# pip install chromadb openai langchain-openai langchain-chroma langchain-core
import os
from typing import List, Dict
from dataclasses import dataclass
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

from backed.agent.factory import embed_model, chat_model

os.environ["OPENAI_API_KEY"] = "your-openai-key"


@dataclass
class ProductDoc:
    content: str
    metadata: Dict


# 1. Mock产品知识库（手机壳相关）
PRODUCT_DOCS = [
    ProductDoc(
        content="我们的手机壳采用进口TPU材质，厚度1.2mm，抗摔性能优秀。通过10米跌落测试，4角全方位保护。",
        metadata={"product": "TPU手机壳", "price": "¥29.9", "color": "透明"}
    ),
    ProductDoc(
        content="这款手机壳支持无线充电，超薄0.8mm设计，不影响信号。防指纹易清洁，完美贴合机身。",
        metadata={"product": "超薄手机壳", "price": "¥39.9", "feature": "无线充电"}
    ),
    ProductDoc(
        content="钢化玻璃后盖手机壳，9H硬度防刮花，前后双层保护。支持MagSafe磁吸。",
        metadata={"product": "钢化玻璃壳", "price": "¥49.9", "feature": "MagSafe"}
    )
]



# 2. 初始化Embeddings + Chroma（本地持久）
embeddings = embed_model
vectorstore = Chroma(
    collection_name="phone_cases",
    embedding_function=embeddings,
    persist_directory="./chroma_db"  # 本地持久
)

# 清空重建（开发用）
vectorstore.delete_collection()
docs = [doc.content for doc in PRODUCT_DOCS]
metadatas = [doc.metadata for doc in PRODUCT_DOCS]
vectorstore.add_texts(docs, metadatas)

llm = chat_model


def product_rag_agent(state: AgentState) -> dict:
    """
    ✅ Chroma RAG + Self-Correction (score<0.5拒答)
    """
    if state["intent"] != "consult":
        return {"messages": [{"role": "assistant", "content": "抱歉，我无法提供相关信息。"}]}

    query = state["messages"][-1]["content"]

    # Retrieve: 带score检索
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3, "fetch_k": 10})
    docs_with_score = retriever.invoke(query)  # Chroma返回带score的Document

    # Self-Correction: 计算平均score
    scores = [doc.metadata.get("score", 0.0) for doc in docs_with_score if doc.metadata.get("score")]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    if avg_score < 0.5:  # 幻觉控制阈值
        response = "抱歉，知识库里没有相关信息，请转人工。"
        return {"messages": [{"role": "assistant", "content": response}]}

    # Generate: 高分文档 → RAG
    context = "\n\n".join([f"来源：{d.metadata}\n内容：{d.page_content}" for d in docs_with_score])

    prompt = ChatPromptTemplate.from_template("""
    根据以下产品信息回答用户问题。信息不足时承认限制。

    上下文：
    {context}

    问题：{query}
    """)
    chain = prompt | llm | StrOutputParser()

    response = chain.invoke({"context": context, "query": query})

    return {
        "messages": [{
            "role": "assistant",
            "content": f"{response}\n\n(检索置信度：{avg_score:.2f})"
        }]
    }