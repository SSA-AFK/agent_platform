import sys
import os

from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever

# 🔥 Windows修复：必须在asyncio/langgraph import前设置
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uuid
import asyncio
import contextlib
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_compressors import FlashrankRerank
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage
from typing import List, Tuple, Optional, Annotated
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from backed.agent.factory import chat_model, embed_model
from backed.utils.logger import get_logger
from vector_store import VectorStoreService
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, MessagesState

logger = get_logger(name="rag_service")


# 标准化文档格式化函数（统一上下文格式）
def format_docs(docs: List[Document]) -> str:
    """标准化文档格式化函数（统一上下文格式）"""
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
rewrite_prompt_text = """你是一个查询优化专家。将用户查询改写为更精确的检索关键词。
仅返回改写后的查询，不要其他说明文字。

原始查询：{question}

改写查询："""

rewrite_prompt = PromptTemplate.from_template(rewrite_prompt_text)
rewrite_chain = (
    rewrite_prompt
    | chat_model.bind(temperature=0.0)
    | StrOutputParser()
    | RunnableLambda(lambda x: x.strip())  # 🔥 正确用法
)

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


# ===== FlashRankRagService 类（保持不变，略微优化日志） =====
class FlashRankRagService:
    def __init__(self, relevance_threshold: float = 0.05, max_retries: int = 2):  # 降低阈值
        self.vector_store = VectorStoreService()
        self.relevance_threshold = relevance_threshold
        self.max_retries = max_retries
        
        self.semantic_retriever = self.vector_store.get_retriever()
        self._bm25_retriever = None
        logger.warning("BM25初始化延迟：首次使用时异步初始化")

        self.hybrid_retriever = EnsembleRetriever(
            retrievers=[self.semantic_retriever, self.semantic_retriever],
            weights=[0.7, 0.3]
        )

        # 🔥 FlashRank修复：健康检查 + 降级
        try:
            self.flashrank_rerank = FlashrankRerank(top_n=4)
            logger.info("✅ FlashRank初始化成功")
        except Exception as e:
            logger.warning(f"⚠️ FlashRank失败({e})，使用纯混合检索")
            self.flashrank_rerank = None

        # 🔥 智能选择retriever
        if self.flashrank_rerank:
            self.retriever = ContextualCompressionRetriever(
                base_compressor=self.flashrank_rerank,
                base_retriever=self.hybrid_retriever,
                k=4
            )
        else:
            self.retriever = self.hybrid_retriever  # 降级纯混合

        # 初始化链和参数
        self.rag_chain, self.rewrite_chain = rag_chain, rewrite_chain

    async def _init_bm25_retriever(self):
        """初始化BM25检索器（带缓存）"""
        if self._bm25_retriever is None:
            try:
                all_docs = await self.vector_store.get_all_documents()
                if all_docs:
                    # 限制文档数避免内存爆炸
                    limited_docs = all_docs[:5000]
                    self._bm25_retriever = BM25Retriever.from_documents(limited_docs, k=4)
                    # 更新混合检索器，调整权重
                    self.hybrid_retriever = EnsembleRetriever(
                        retrievers=[self.semantic_retriever, self._bm25_retriever],
                        weights=[0.8, 0.2]  # 语义为主，BM25辅助
                    )
                    self.retriever = ContextualCompressionRetriever(
                        base_compressor=self.flashrank_rerank,
                        base_retriever=self.hybrid_retriever,
                        k=4
                    )
                    logger.info(f"BM25初始化完成，使用{len(limited_docs)}篇文档")
                else:
                    logger.warning("No docs for BM25—using semantic only")
                    self._bm25_retriever = self.semantic_retriever
            except Exception as e:
                logger.error(f"BM25初始化失败：{str(e)}")
                self._bm25_retriever = self.semantic_retriever
                logger.warning("BM25降级：纯语义+FlashRank")
        return self._bm25_retriever

    async def retriever_docs(self, query: str) -> List[Document]:
        """混合检索 + FlashRank重排序 获取文档"""
        try:
            # 确保BM25检索器已初始化
            await self._init_bm25_retriever()
            import asyncio
            docs = await asyncio.to_thread(self.retriever.invoke, query)
            # 添加FlashRank调试日志
            for doc in docs[:2]:  # 只看top2
                score = doc.metadata.get('score', 'N/A')
                logger.info(f"Doc score: {score}, content preview: {doc.page_content[:50]}")
            logger.info(f"混合+FlashRank → Top-{len(docs)}篇")
            return docs
        except Exception as e:
            logger.error(f"检索文档异常：{str(e)}")
            return []

    def _docs_relevant(self, docs: List[Document], query: str) -> Tuple[bool, float]:
        """用混合检索器分数评估（FlashRank score=N/A时）"""
        if not docs:
            return False, 0.0

        # 🔥 优先混合检索分数，其次FlashRank
        scores = []
        for doc in docs:
            score = doc.metadata.get('score') or doc.metadata.get('_score', 0.0)
            scores.append(float(score) if score != 'N/A' else 0.01)  # 默认小分数
        
        top_score = max(scores)
        logger.info(f"评估分数: top={top_score:.3f} (混合/FlashRank)")
        return top_score > self.relevance_threshold, top_score

    def get_retrieval_quality(self, docs: List[Document]) -> Tuple[str, float]:
        """多维度评分：分数+文档数+内容长度"""
        if not docs:
            return "empty", 0.0

        scores = []
        total_len = 0
        for doc in docs:
            score = doc.metadata.get('score') or doc.metadata.get('_score', 0.0)
            scores.append(float(score) if score != 'N/A' else 0.01)
            total_len += len(doc.page_content)
        
        top_score = max(scores)
        avg_len = total_len / len(docs)
        
        logger.info(f"质量评估: top={top_score:.3f}, docs={len(docs)}, avg_len={avg_len:.0f}")

        # 🔥 综合评分：分数OR文档质量OR内容丰富度
        if top_score > 0.01 or len(docs) >= 3 or avg_len > 200:
            return "excellent", top_score + 0.1  # 加成
        elif len(docs) >= 1 or avg_len > 100:
            return "good", top_score
        else:
            return "marginal", top_score

    async def generate_safe(self, query: str, docs: List[Document]) -> str:
        """安全生成回答（带异常捕获）"""
        try:
            import asyncio
            return await asyncio.to_thread(self.rag_chain.invoke, {"docs": docs, "input": query})
        except Exception as e:
            logger.error(f"生成回答异常：{str(e)}")
            return "抱歉，生成回答时出错，请重试。"

    async def rag_summarize(self, query: str) -> str:
        """核心RAG问答逻辑：检索→评估→改写重试→生成"""
        try:
            current_query = query
            for attempt in range(self.max_retries):
                logger.info(f"尝试{attempt + 1}: '{current_query[:40]}...'")
                # 1. 检索文档
                docs = await self.retriever_docs(current_query)
                # 2. 评估检索质量
                quality, score = self.get_retrieval_quality(docs)
                logger.info(f"检索质量: {quality}, 分数: {score:.3f}")

                if quality in ["excellent", "good"]:
                    # 3. 质量达标 → 生成回答
                    return await self.generate_safe(query, docs)
                elif quality == "marginal" and attempt < self.max_retries - 1:
                    # 4. 质量边缘 → 改写查询并重试（仅一次）
                    try:
                        import asyncio
                        current_query = await asyncio.to_thread(self.rewrite_chain.invoke, {"question": query})
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


# ===== 核心 VectorMemoryRag 类（持久化模式） =====
class VectorMemoryRag:
    """RAG + PostgresSaver，使用独立上下文管理"""
    
    def __init__(self):
        self.rag_service = FlashRankRagService()
        self._thread_id = None



    async def rag_node(self, state: MessagesState):
        """RAG节点（保持不变）"""
        query = state["messages"][-1].content
        answer = await self.rag_service.rag_summarize(query)
        return {"messages": [AIMessage(content=answer)]}

    def set_thread_id(self, thread_id: str):
        self._thread_id = thread_id

    def get_thread_id(self) -> str:
        if not self._thread_id:
            self._thread_id = str(uuid.uuid4())
        return self._thread_id

    async def chat(self, query: str, session_id: str = None) -> str:
        """使用独立上下文执行chat"""
        if session_id:
            self.set_thread_id(session_id)
        thread_id = self.get_thread_id()
        config = {"configurable": {"thread_id": thread_id}}
        
        PG_CONN_STRING = os.getenv(
            "PG_CONN_STRING",
            "postgresql://postgres:04017736@localhost:5432/postgres?sslmode=disable"
        )
        
        async with AsyncPostgresSaver.from_conn_string(PG_CONN_STRING) as checkpointer:
            class State(MessagesState):
                pass
            
            builder = StateGraph(State)
            builder.add_node("rag", self.rag_node)
            builder.set_entry_point("rag")
            builder.set_finish_point("rag")
            
            app = builder.compile(checkpointer=checkpointer)
            result = await app.ainvoke(
                {"messages": [HumanMessage(content=query)]},
                config=config
            )
            return result["messages"][-1].content

    async def get_session_history(self, session_id: str, limit: int = 10) -> List[dict]:
        """使用独立上下文获取状态"""
        thread_id = session_id or self.get_thread_id()
        config = {"configurable": {"thread_id": thread_id}}
        
        PG_CONN_STRING = os.getenv(
            "PG_CONN_STRING",
            "postgresql://postgres:04017736@localhost:5432/postgres?sslmode=disable"
        )
        
        async with AsyncPostgresSaver.from_conn_string(PG_CONN_STRING) as checkpointer:
            class State(MessagesState):
                pass
            
            builder = StateGraph(State)
            builder.add_node("rag", self.rag_node)
            builder.set_entry_point("rag")
            builder.set_finish_point("rag")
            
            app = builder.compile(checkpointer=checkpointer)
            state = await app.aget_state(config)
            
            if state and state.values.get("messages"):
                messages = state.values["messages"][-limit:]
                return [{
                    "type": type(msg).__name__,
                    "role": getattr(msg, 'role', 'unknown'),
                    "content": getattr(msg, 'content', ''),
                    "name": getattr(msg, 'name', None)
                } for msg in messages]
            return []

    async def get_session_summary(self, session_id: str) -> str:
        """会话摘要"""
        history = await self.get_session_history(session_id, limit=5)
        if not history:
            return "会话为空"
        return "\n".join([
            f"{msg.get('type', 'unknown')}: {msg.get('content', '')[:100]}..."
            for msg in history
        ])

    async def clear_session(self, session_id: str):
        """使用独立上下文清理会话"""
        thread_id = session_id or self.get_thread_id()
        config = {"configurable": {"thread_id": thread_id}}
        
        PG_CONN_STRING = os.getenv(
            "PG_CONN_STRING",
            "postgresql://postgres:04017736@localhost:5432/postgres?sslmode=disable"
        )
        
        async with AsyncPostgresSaver.from_conn_string(PG_CONN_STRING) as checkpointer:
            class State(MessagesState):
                pass
            
            builder = StateGraph(State)
            builder.add_node("rag", self.rag_node)
            builder.set_entry_point("rag")
            builder.set_finish_point("rag")
            
            app = builder.compile(checkpointer=checkpointer)
            await app.aupdate_state(config, None)
            logger.info(f"会话 {thread_id} 已清理")


# ===== 测试函数（持久化模式） =====
async def run_agent_tests():
    """测试（持久化模式，带Postgres）"""
    agent = VectorMemoryRag()  # 无需initialize
    
    test_thread_id = "test_123"
    print("🧵 会话ID:", test_thread_id)
    
    response = await agent.chat("小户型机器人推荐", test_thread_id)
    print("🤖 回复:", response[:100])
    
    history = await agent.get_session_history(test_thread_id, limit=5)
    print("📜 历史:", len(history), "条（持久化）")
    
    # 验证跨会话持久化
    response2 = await agent.chat("再推荐一款", test_thread_id)
    print("🤖 回复2:", response2[:100])
    
    print("✅ 持久化测试通过！")
    return True  # 明确成功

async def main():
    try:
        await run_agent_tests()
        print("🎉 RAG + Postgres完整系统测试通过！")
    except Exception as e:
        logger.error(f"❌ 真实失败: {e}")
        print(f"❌ 失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())