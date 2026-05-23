from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_compressors import FlashrankRerank
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel, RunnableLambda
from typing import List, Tuple, Optional

from backed.agent.factory import chat_model
from backed.utils.logger import get_logger
from vector_store import VectorStoreService
from langchain_core.prompts import PromptTemplate

logger = get_logger(name="rag_service")

# 标准化文档格式化函数（统一上下文格式）
def format_docs(docs: List[Document]) -> str:
    """标准化文档格式化函数（统一上下文格式）"""
    formatted_context = []
    for i, doc in enumerate(docs):
        # 补充文档元数据（如来源、页码），提升回答可信度
        meta_info = f"来源：{doc.metadata.get('source', '未知')}" if doc.metadata else ""
        formatted_context.append(f"【{i+1}】{meta_info}\n{doc.page_content}")
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
    def __init__(self, relevance_threshold: float = 0.5, max_retries: int = 3):
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
        self.flashrank_rerank = FlashrankRerank()  # 默认模型：ms-marco-MiniLM-L-6-v2
        self.retriever = ContextualCompressionRetriever(
            base_compressor=self.flashrank_rerank,
            base_retriever=self.hybrid_retriever,
            k=4  # 最终只保留Top4文档
        )

        # 初始化链和参数
        self.rag_chain, self.rewrite_chain, self.relevance_chain = rag_chain, rewrite_chain, relevance_chain
        self.relevance_threshold = relevance_threshold  # 相关性阈值（0.5）
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
        """评估检索文档与问题的相关性"""
        if not docs:
            return False, 0.0
        scores = []
        for doc in docs[:3]:  # 评估前3篇
            doc_content = doc.page_content[:2000]  # 截断避免超长
            try:
                score = self.relevance_chain.invoke({"question": query, "doc_content": doc_content})
                scores.append(score)
            except Exception as e:
                logger.error(f"评估相关性异常：{str(e)}")
                scores.append(0.0)
        avg_score = sum(scores) / len(scores)
        logger.info(f"平均相关性评分: {avg_score:.2f}")
        return avg_score > self.relevance_threshold, avg_score

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
            attempts = 0

            while attempts < self.max_retries:
                logger.info(f"尝试{attempts + 1}: '{current_query[:40]}...'")
                # 1. 检索文档
                docs = self.retriever_docs(current_query)
                # 2. 评估相关性
                is_relevant, score = self._docs_relevant(docs, query)

                if is_relevant:
                    # 3. 相关性达标 → 生成回答
                    return self.generate_safe(query, docs)

                # 4. 相关性不达标 → 改写查询并重试
                attempts += 1
                if attempts < self.max_retries:
                    try:
                        current_query = self.rewrite_chain.invoke({"question": query})
                        logger.info(f"查询改写为：{current_query[:40]}...")
                    except Exception as e:
                        logger.error(f"查询改写异常：{str(e)}")
                        return "抱歉，处理请求时出错，请稍后重试。"
                else:
                    logger.info("经过多次尝试，未找到相关资料")
                    return "抱歉，经过混合检索+重排序，仍未找到相关资料。"
        except Exception as e:
            logger.error(f"RAG处理异常：{str(e)}", exc_info=True)
            return "抱歉，处理请求时出错，请稍后重试。"

# 向量记忆库实现（方案3）
class VectorMemoryRag:
    def __init__(self):
        self.rag_service = FlashRankRagService()
        self.memory_store = VectorStoreService()  # 新建记忆专用索引
        
    def chat(self, query: str, session_id: str = "default") -> str:
        """带记忆的对话接口"""
        try:
            # 1. 检索相关历史（带session过滤）
            history_docs = self.memory_store.similarity_search(
                f"{session_id}: {query}", k=3
            )
            
            # 2. 合并历史+知识库检索
            context = "\n".join([d.page_content for d in history_docs])
            knowledge_docs = self.rag_service.retriever_docs(query)
            full_context = context + "\n---\n" + "\n".join([d.page_content for d in knowledge_docs])
            
            # 3. 生成回答
            answer = self.rag_service.generate_safe(query, knowledge_docs)
            
            # 4. 保存本次对话到记忆
            memory_doc = Document(
                page_content=f"Q: {query}\nA: {answer}",
                metadata={"session_id": session_id, "timestamp": "now"}
            )
            self.memory_store.add_documents([memory_doc])
            
            return answer
        except Exception as e:
            logger.error(f"VectorMemoryRag.chat异常：{str(e)}")
            return "抱歉，处理请求时出错，请稍后重试。"

# 测试代码
if __name__ == '__main__':
    # 测试基础RAG
    rag = FlashRankRagService(relevance_threshold=0.5)
    logger.info("测试1: 正常查询")
    result1 = rag.rag_summarize("小户型适合哪些扫地机器人")
    logger.info(f"测试1结果: {result1[:100]}...")
    print(result1)
    
    logger.info("\n测试2: 挑战查询")
    result2 = rag.rag_summarize("RAG混合检索FlashRank实现")
    logger.info(f"测试2结果: {result2[:100]}...")
    print(result2)
    
    # 测试向量记忆库
    logger.info("\n测试3: 向量记忆库")
    vm_rag = VectorMemoryRag()
    answer1 = vm_rag.chat("RAG是什么？", "user_123")
    logger.info(f"测试3-1结果: {answer1[:100]}...")
    print(answer1)
    
    answer2 = vm_rag.chat("你刚才说的RAG怎么优化？", "user_123")  # 自动召回历史
    logger.info(f"测试3-2结果: {answer2[:100]}...")
    print(answer2)


