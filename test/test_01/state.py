import os

from langgraph.checkpoint.postgres import PostgresSaver

from backed.agent.factory import embed_model, chat_model
from typing import TypedDict, Annotated, List, Union, Dict
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END, START
from langgraph.types import Command, interrupt
import operator
from dataclasses import dataclass
import numpy as np
import re

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "production-agent"


@dataclass
class ProductDoc:
    content: str
    metadata: Dict

PRODUCT_DOCS = [  # ... 你的 PRODUCT_DOCS 数据不变
    ProductDoc(content="我们的手机壳采用进口TPU材质，厚度1.2mm，抗摔性能优秀。通过10米跌落测试，4角全方位保护。", metadata={"product": "TPU手机壳", "price": "¥29.9", "color": "透明"}),
    ProductDoc(content="这款手机壳支持无线充电，超薄0.8mm设计，不影响信号。防指纹易清洁，完美贴合机身。", metadata={"product": "超薄手机壳", "price": "¥39.9", "feature": "无线充电"}),
    ProductDoc(content="钢化玻璃后盖手机壳，9H硬度防刮花，前后双层保护。支持MagSafe磁吸。", metadata={"product": "钢化玻璃壳", "price": "¥49.9", "feature": "MagSafe"})
]

# Chroma 初始化不变
embeddings = embed_model
vectorstore = Chroma(collection_name="phone_cases", embedding_function=embeddings, persist_directory="./chroma_db")
docs = [doc.content for doc in PRODUCT_DOCS]
metadatas = [doc.metadata for doc in PRODUCT_DOCS]
vectorstore.add_texts(docs, metadatas)

class AgentState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], operator.add]
    order_id: Union[str, None]
    intent: str
    human_needed: bool
    human_approved: str

llm = chat_model


def intent_classifier(state: AgentState) -> dict:
    """意图分类 + 提取订单号"""
    last_message = state["messages"][-1].content
    order_id = re.search(r"ORD-\d+", last_message).group() if re.search(r"ORD-\d+", last_message) else None
    if order_id:
        print(f"✅ 提取到订单号: {order_id}")

    # 意图判断
    if "产品" in last_message or "手机壳" in last_message:
        intent = "consult"
    elif "物流" in last_message or "快递" in last_message:
        intent = "logistics"
    elif "退" in last_message or "退款" in last_message:
        intent = "refund"
    else:
        intent = "chat"

    return {
        "intent": intent,
        "order_id": order_id,
        "messages": [AIMessage(content=f"已识别意图：{intent}")]
    }


def product_rag_agent(state: AgentState) -> dict:
    """产品咨询 RAG 节点"""
    if state.get("intent") != "consult":
        return {"messages": [AIMessage(content="抱歉，我无法提供相关信息。")]}

    query = state["messages"][-2].content  # 取用户原始问题
    docs_with_score = vectorstore.similarity_search_with_score(query, k=3)

    # 归一化相似度得分
    EMBEDDING_DIM = 384
    max_possible_dist = np.sqrt(EMBEDDING_DIM) * np.sqrt(2)
    scores = [1 - (dist / max_possible_dist) for doc, dist in docs_with_score] if docs_with_score else []
    avg_score = sum(scores) / len(scores) if scores else 0.0

    if avg_score < 0.5:
        return {"messages": [AIMessage(content="抱歉，知识库里没有相关信息，请转人工。")]}

    context = "\n\n".join([f"来源：{doc.metadata}\n内容：{doc.page_content}" for doc, _ in docs_with_score])
    prompt = ChatPromptTemplate.from_template("""
    根据以下产品信息简洁回答用户问题，只说关键信息。
    上下文：{context}
    问题：{query}
    """)
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"context": context, "query": query})

    return {
        "messages": [AIMessage(content=f"{response}\n\n(检索置信度：{avg_score:.2f})")]
    }


def order_status_agent(state: AgentState) -> dict:
    """物流查询节点"""
    if state.get("intent") != "logistics":
        return {"messages": [AIMessage(content="当前不支持此操作。")]}

    order_id = state.get("order_id")
    response = f"订单 {order_id} 物流状态：已到达深圳转运中心，预计24小时内送达。" if order_id else "请提供订单号（格式如 ORD-123）"
    return {"messages": [AIMessage(content=response)]}


def refund_manager(state: AgentState) -> dict:
    """退款审批节点"""
    interrupt_data = {
        "type": "refund_approval",
        "order_id": state.get("order_id"),
        "query": "请审批退款申请？回复 'approve' / 'reject'",
    }

    # ✅ 返回interrupt，人类输入会成为此节点的返回值
    human_decision = interrupt(interrupt_data)
    return {"human_approved": human_decision}  # ✅ 将人类输入存入state


def refund_executor(state: AgentState) -> dict:
    """退款执行（直接从state获取人类决策）"""
    human_response = state.get("human_approved", "reject")
    print(f"👤 人工决策: {human_response}")

    if human_response.lower() != "approve":
        return {"messages": [AIMessage(content="❌ 退款被拒绝，请联系客服。")]}

    order_id = state.get("order_id")
    return {"messages": [AIMessage(content=f"✅ 退款成功！订单 {order_id} 将3-5天到账。")]}


def casual_chat_agent(state: AgentState) -> dict:
    """普通聊天节点：带记忆功能，使用完整历史对话上下文"""
    # 过滤掉分类器的"已识别意图"消息（只保留用户和助手的真实对话）
    history_messages = []
    for msg in state["messages"]:
        # 只保留 HumanMessage/AIMessage，跳过分类器的辅助消息
        if isinstance(msg, (HumanMessage, AIMessage)) and "已识别意图：" not in msg.content:
            history_messages.append(msg)

    # 构建带历史的聊天提示词
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个友好的客服助手，有记忆功能，。
        回答要简洁、亲切，结合历史对话上下文，不要重复提问，不要提及产品信息（除非用户主动问）。"""),
        # 插入历史对话
        ("placeholder", "{chat_history}"),
        # 当前用户问题
        ("human", "{current_question}")
    ])

    # 提取当前用户的最后一条问题
    current_question = history_messages[-1].content if history_messages else ""

    # 调用LLM生成回复（传入历史+当前问题）
    chain = chat_prompt | llm | StrOutputParser()
    chat_response = chain.invoke({
        "chat_history": history_messages[:-1],  # 历史对话（排除当前问题）
        "current_question": current_question
    })

    return {
        "messages": [AIMessage(content=chat_response)]
    }
def route_intent(state: AgentState) -> str:
    """意图路由函数"""
    intent = state.get("intent", "chat")
    mapping = {"consult": "product_expert", "logistics": "logistics_bot", "refund": "refund_manager", "chat": "chat"}
    return mapping.get(intent, END)


# ===================== 构建工作流 =====================
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("classifier", intent_classifier)
workflow.add_node("product_expert", product_rag_agent)
workflow.add_node("logistics_bot", order_status_agent)
workflow.add_node("refund_manager", refund_manager)
workflow.add_node("refund_executor", refund_executor)
workflow.add_node("chat", casual_chat_agent)

# 定义边
workflow.add_edge(START, "classifier")
workflow.add_conditional_edges(
    "classifier",route_intent,
    {
    "product_expert": "product_expert",
     "logistics_bot": "logistics_bot",
     "refund_manager": "refund_manager",
     "chat":"chat",END: END
}
)
workflow.add_edge("product_expert", END)
workflow.add_edge("logistics_bot", END)
workflow.add_edge("refund_manager", "refund_executor")
workflow.add_edge("refund_executor", END)
workflow.add_edge("chat", END)

# 编译工作流
checkpointer = MemorySaver()
app = workflow.compile(
    checkpointer=checkpointer,
)

# ===================== 测试运行（核心修复：异常捕获）=====================
if __name__ == "__main__":

    # config = {"configurable": {"thread_id": "test1"}}
    #
    # # 第一轮：用户自我介绍
    # print("=== 第一轮对话 ===")
    # result1 = app.invoke(
    #     {"messages": [HumanMessage(content="hello，我是小明，你是谁？")]},
    #     config=config
    # )
    # # 只打印关键消息（过滤分类器辅助消息）
    # for msg in result1["messages"]:
    #     if isinstance(msg, (HumanMessage, AIMessage)) and "已识别意图：" not in msg.content:
    #         print(f"{msg.type.upper()}: {msg.content}")
    #
    # print("\n=== 第二轮对话（测试记忆）===")
    # # 第二轮：问名字（同一个thread_id，共享记忆）
    # result2 = app.invoke(
    #     {"messages": [HumanMessage(content="你知道我是谁吗？")]},  # 注意：这里不用传历史，checkpointer会自动加载
    #     config=config
    # )
    # # 只打印关键消息
    # for msg in result2["messages"]:
    #     if isinstance(msg, (HumanMessage, AIMessage)) and "已识别意图：" not in msg.content:
    #         print(f"{msg.type.upper()}: {msg.content}")

    mermaid_code = app.get_graph().draw_mermaid()
    print("复制以下代码到 https://mermaid.live/ 查看图片：")
    print(mermaid_code)