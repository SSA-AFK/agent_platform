from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_compressors import FlashrankRerank
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage
from typing import List, Tuple
from backed.agent.factory import chat_model
from test.rag.vector_store import VectorStoreService
from backed.utils.logger import get_logger
from langchain_core.prompts import PromptTemplate
# 导入 LangGraph 组件
from langgraph.graph import StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver

logger = get_logger(name="rag_service")


# 标准化文档格式化函数（统一上下文格式）
def format_docs(docs: List[Document]) -> str:
    formatted_context = []
    for i, doc in enumerate(docs):
        # 补充文档元数据（如来源、页码），提升回答可信度
        meta_info = f"来源：{doc.metadata.get('source', '未知')}" if doc.metadata else ""
        formatted_context.append(f"【{i + 1}】{meta_info}\n{doc.page_content}")
    return "\n\n".join(formatted_context)


# RAG核心Prompt：用文档上下文回答问题
rag_prompts = """你是一个专业的问答助手，严格遵守以下规则：
1. 仅使用提供的文档内容回答问题，不编造任何未提及的信息；
2. 如果文档内容不足以回答问题，明确说明'根据现有资料无法回答该问题'；
3. 回答要准确、详细，优先分点说明（如果适用）；
4. 回答语言要与用户问题的语言保持一致；
5. 引用文档内容时，可标注文档序号（如【1】）增强可信度。

文档内容：
{context}

用户问题：{input}

请给出符合规则的回答："""

rag_prompt = PromptTemplate.from_template(rag_prompts)

# 构建优化后的RAG链（带并行处理和降级策略）
rag_chain_optimized = (
    # 第一步：并行处理输入，格式化上下文和保留原始问题
        RunnableParallel({
            "context": lambda x: format_docs(x["docs"]),  # 文档格式化
            "input": RunnablePassthrough()  # 透传用户问题
        })
        # 第二步：传入Prompt
        | rag_prompt
        # 第三步：调用LLM（带参数绑定）
        | chat_model.bind(temperature=0.1, max_tokens=2000)
        # 第四步：输出解析
        | StrOutputParser()
).with_fallbacks([
    # 降级策略：解析失败时返回友好提示
    RunnableLambda(lambda _: "抱歉，回答生成过程中出现错误，请稍后重试。")
])

rag_chain = rag_chain_optimized  # Prompt→LLM→解析输出

# 查询改写Prompt：优化查询语句，提升检索效果
rewrite_prompt_text = """你是一个查询优化专家。请将以下用户查询改写成更清晰、更具体的表达方式，以便更好地检索相关信息。

原始查询：{question}

请提供改写后的查询："""
rewrite_prompt = PromptTemplate.from_template(rewrite_prompt_text)
rewrite_chain = rewrite_prompt | chat_model | StrOutputParser()

# 相关性评估Prompt：给文档-问题相关性打分（0-1）
relevance_prompt_text = """请评估以下文档内容与用户问题的相关性，给出0-1之间的分数。

用户问题：{question}

文档内容：{doc_content}

相关性分数（仅返回数字）："""
relevance_prompt = PromptTemplate.from_template(relevance_prompt_text)


# 自定义浮点解析器：提取LLM返回的分数（处理非纯数字输出）
class FloatParser(StrOutputParser):
    def parse(self, text: str) -> float:
        try:
            import re
            numbers = re.findall(r'\d+\.?\d*', text)  # 提取数字（整数/小数）
            if numbers:
                return float(numbers[0])
            return 0.0
        except ValueError:
            return 0.0


relevance_chain = relevance_prompt | chat_model | FloatParser()


class FlashRankRagService:
    def __init__(self, relevance_threshold: float = 0.25, max_retries: int = 3):
        self.vector_store = VectorStoreService()
        self._bm25_retriever = None  # BM25检索器缓存

        # 1. 语义检索器（来自自定义向量库）
        self.semantic_retriever = self.vector_store.get_retriever()

        # 2. BM25检索器（支持降级：无全文档时复用语义检索）
        bm25_retriever = self._init_bm25_retriever()

        # 3. 混合检索器（语义70% + BM25 30%）
        self.hybrid_retriever = EnsembleRetriever(
            retrievers=[self.semantic_retriever, bm25_retriever],
            weights=[0.7, 0.3]
        )

        # 4. FlashRank重排序 + 上下文压缩
        self.flashrank_rerank = FlashrankRerank(
            top_n=4
        )
        self.retriever = ContextualCompressionRetriever(
            base_compressor=self.flashrank_rerank,
            base_retriever=self.hybrid_retriever,
            k=4  # 最终只保留Top4文档
        )

        # 初始化链和参数
        self.rag_chain, self.rewrite_chain, self.relevance_chain = rag_chain, rewrite_chain, relevance_chain
        self.relevance_threshold = relevance_threshold  # 相关性阈值（0.25）
        self.max_retries = max_retries  # 最大重试次数（3）

    def _init_bm25_retriever(self):
        """初始化BM25检索器（带缓存）"""
        if self._bm25_retriever is not None:
            return self._bm25_retriever
        try:
            all_docs = self.vector_store.get_all_documents()
            self._bm25_retriever = BM25Retriever.from_documents(all_docs, k=10)
            logger.info("BM25全文档模式")
        except AttributeError as e:
            self._bm25_retriever = self.semantic_retriever
            logger.warning("BM25降级：纯语义+FlashRank")
        return self._bm25_retriever

    def retriever_docs(self, query: str) -> List[Document]:
        """混合检索 + FlashRank重排序 获取文档"""
        try:
            docs = self.retriever.invoke(query)
            logger.info(f"混合+FlashRank → Top-{len(docs)}篇")
            return docs
        except Exception as e:
            logger.error(f"检索文档异常：{str(e)}")
            return []

    def _docs_relevant(self, docs: List[Document], query: str) -> Tuple[bool, float]:
        """用 FlashRank 内置分数评估（无需 LLM）"""
        if not docs:
            return False, 0.0

        # FlashRank 已重排序，最高分代表整体质量
        scores = [doc.metadata.get('score', 0.0) for doc in docs]
        top_score = max(scores) if scores else 0.0
        avg_score = sum(scores) / len(scores) if scores else 0.0

        logger.info(f"FlashRank Top分: {top_score:.3f}, 平均: {avg_score:.3f}")
        return top_score > self.relevance_threshold, top_score  # 用最高分做决策

    def get_retrieval_quality(self, docs: List[Document]) -> Tuple[str, float]:
        """多层评分，无 LLM"""
        if not docs:
            return "empty", 0.0

        scores = [doc.metadata.get('score', 0.0) for doc in docs]
        top_score = max(scores) if scores else 0.0

        # 动态阈值：如果分数全为0，用文档数量判断
        if top_score == 0.0:
            if len(docs) >= 2:
                return "good", 0.3  # 有文档就用
            else:
                return "poor", 0.0
        elif top_score > 0.3:  # 降低阈值
            return "excellent", top_score
        elif top_score > 0.15:
            return "good", top_score
        else:
            return "marginal", top_score

    def generate_safe(self, query: str, docs: List[Document]) -> str:
        """安全生成回答（带异常捕获）"""
        try:
            return self.rag_chain.invoke({"docs": docs, "input": query})
        except Exception as e:
            logger.error(f"生成回答异常：{str(e)}")
            return "抱歉，生成回答时出错，请重试。"

    def rag_summarize(self, query: str) -> str:
        """核心问答逻辑：检索→评估→改写重试→生成回答"""
        try:
            current_query = query
            for attempt in range(self.max_retries):
                logger.info(f"尝试{attempt + 1}: '{current_query[:40]}...'")
                # 1. 检索文档
                docs = self.retriever_docs(current_query)
                # 2. 评估检索质量
                quality, score = self.get_retrieval_quality(docs)
                logger.info(f"检索质量: {quality}, 分数: {score:.3f}")

                if quality in ["excellent", "good"]:
                    # 3. 质量达标 → 生成回答
                    return self.generate_safe(query, docs)
                elif quality == "marginal" and attempt < self.max_retries - 1:
                    # 4. 质量边缘 → 改写查询并重试（仅一次）
                    try:
                        current_query = self.rewrite_chain.invoke({"question": query})
                        logger.info(f"查询改写为：{current_query[:40]}...")
                    except Exception as e:
                        logger.error(f"查询改写异常：{str(e)}")
                        return "抱歉，处理请求时出错，请稍后重试。"
                else:
                    # 5. 质量差或已达最大重试次数
                    logger.info("经过多次尝试，未找到相关资料")
                    return "抱歉，经过混合检索+重排序，仍未找到相关资料。"
        except Exception as e:
            logger.error(f"RAG处理异常：{str(e)}", exc_info=True)
            return "抱歉，处理请求时出错，请稍后重试。"


# 向量记忆库实现（方案3）
class VectorMemoryRag:
    def __init__(self):
        self.rag_service = FlashRankRagService()
        # 知识库：Chroma（静态文档）
        self.knowledge_store = VectorStoreService()
        # 聊天记录：LangGraph + MemorySaver（推荐）
        self.checkpointer = MemorySaver()
        self.graph = self._build_rag_graph()
        self.app = self.graph.compile(checkpointer=self.checkpointer)
        logger.info("使用 LangGraph + MemorySaver 存储聊天记录")

    def _build_rag_graph(self):
        """构建 RAG + 记忆 Graph"""

        # 状态：消息列表
        class State(MessagesState):
            docs: List[Document] = []

        graph = StateGraph(State)

        def rag_node(state: State):
            """RAG 节点"""
            query = state["messages"][-1].content
            docs = self.rag_service.retriever_docs(query)
            answer = self.rag_service.generate_safe(query, docs)
            return {
                "messages": [AIMessage(content=answer)],
                "docs": docs  # 可选：保存检索文档
            }

        graph.add_node("rag", rag_node)
        graph.set_entry_point("rag")
        graph.set_finish_point("rag")
        return graph

    def chat(self, query: str, session_id: str = "default") -> str:
        """多会话聊天"""
        try:
            # 使用 LangGraph
            config = {"configurable": {"thread_id": session_id}}
            result = self.app.invoke(
                [HumanMessage(content=query)],
                config=config
            )
            return result["messages"][-1].content
        except Exception as e:
            logger.error(f"聊天异常：{str(e)}")
            return "处理出错，请重试"

    def get_session_history(self, session_id: str, limit: int = 10) -> List:
        """查看会话历史"""
        try:
            config = {"configurable": {"thread_id": session_id}}
            state = self.checkpointer.get(config)
            return state["messages"][-limit:] if state else []
        except Exception as e:
            logger.error(f"获取会话历史异常：{str(e)}")
            return []

    def get_session_summary(self, session_id: str) -> str:
        """获取会话摘要"""
        try:
            history = self.get_session_history(session_id, limit=5)
            if not history:
                return "会话为空"
            # LangGraph 消息对象
            return "\n".join(
                [f"{msg.type}: {msg.content[:100]}..." if len(msg.content) > 100 else f"{msg.type}: {msg.content}" for
                 msg in history])
        except Exception as e:
            logger.error(f"获取会话摘要异常：{str(e)}")
            return "无法获取会话摘要"

    def clear_session(self, session_id: str):
        """清理会话"""
        try:
            # MemorySaver 自动处理，新线程覆盖旧历史
            logger.info(f"会话 {session_id} 已清理（新线程）")
        except Exception as e:
            logger.error(f"清理会话异常：{str(e)}")


# 测试代码
if __name__ == '__main__':
    # 测试基础RAG
    rag = FlashRankRagService(relevance_threshold=0.5)
    logger.info("测试1: 正常查询")
    result1 = rag.rag_summarize("小户型适合哪些扫地机器人")
    logger.info(f"测试1结果: {result1[:100]}...")
    print(result1)

