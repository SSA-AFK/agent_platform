from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Interrupt, interrupt
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import operator
from uuid import uuid4


# 状态定义
class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    sql_query: str
    approved: bool | None
    decision: str | None  # 人类决策存储
    human_decision: str | None  # 存储恢复时传入的人类决策


# 节点1: 生成SQL查询
def generate_query(state: State) -> dict:
    """生成需要审批的SQL查询"""
    query = "DELETE FROM users WHERE last_login < '2023-01-01'"
    return {
        "messages": [AIMessage(content=f"🤖 生成SQL查询:\n```sql\n{query}\n```")],
        "sql_query": query
    }


# 节点2: 人类审批（抛出中断）
def human_approval(state: State) -> dict:
    print("执行到human_approval77777777777777777777777777777")
    query = state["sql_query"]

    # 抛出中断，等待人类输入
    return interrupt({
        "type": "sql_approval",
        "query": query,
        "instructions": "回复: 'approve'批准 / 'reject'拒绝"
    })


# 节点3: 处理人类决策（仅接收state参数）
def handle_human_decision(state: State) -> dict:
    """处理恢复时传入的人类决策"""
    human_decision = state.get("human_decision", "reject")
    print(f"人类决策: {human_decision}")

    if human_decision == "approve":
        return {
            "messages": [HumanMessage(content="✅ 查询已批准")],
            "approved": True,
            "decision": human_decision
        }
    else:
        return {
            "messages": [HumanMessage(content="❌ 查询被拒绝")],
            "approved": False,
            "decision": human_decision
        }


# 节点4: 执行SQL
def execute_sql(state: State) -> dict:
    """仅批准后执行"""
    if not state.get("approved"):
        return {
            "messages": [AIMessage(content="⏭️ 跳过执行（未批准）")]
        }

    query = state["sql_query"]
    # 模拟执行
    result = f"✅ 执行成功！删除了15条记录\n查询: {query}"
    return {"messages": [AIMessage(content=result)]}


# 条件边：根据是否中断恢复决定下一步
def should_handle_decision(state: State) -> str:
    """判断是否需要处理人类决策"""
    if state.get("human_decision"):
        return "handle_decision"
    return "human_approval"


# 构建图
workflow = StateGraph(State)
workflow.add_node("generate", generate_query)
workflow.add_node("human_approval", human_approval)
workflow.add_node("handle_decision", handle_human_decision)
workflow.add_node("execute", execute_sql)

# 边定义
workflow.add_edge(START, "generate")
# 生成SQL后，根据状态决定是中断还是处理决策
workflow.add_conditional_edges(
    "generate",
    should_handle_decision,
    {
        "human_approval": "human_approval",
        "handle_decision": "handle_decision"
    }
)
workflow.add_edge("handle_decision", "execute")
workflow.add_edge("execute", END)

# 编译（必须有checkpointer）
checkpointer = MemorySaver()
app = workflow.compile(
    checkpointer=checkpointer,
)


# ========== 完整运行演示 ==========
def run_demo():
    # 生成唯一的线程ID
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # 第1步：运行到中断
    print("=== 第1步：生成SQL并中断 ===")
    try:
        result1 = app.invoke({"messages": []}, config)
    except Exception as e:
        # 捕获中断，获取中断信息
        if hasattr(e, 'metadata'):
            print(f"中断类型: {e.metadata['type']}")
            print(f"待审批SQL: {e.metadata['query']}")
            print(f"操作指引: {e.metadata['instructions']}")
        else:
            raise

    # 模拟人类审核（实际场景中这里是前端/人工输入）
    human_input = "reject"  # 可以改为 "reject" 测试拒绝流程
    print(f"\n=== 人类审核结果：{human_input} ===")

    # 第2步：恢复中断并处理决策
    print("\n=== 第2步：恢复流程处理决策 ===")

    # 传入人类决策，恢复流程
    resume_inputs = {
        "human_decision": human_input,
        # 标记为恢复模式
        "__interrupt_resume__": True
    }

    # 使用invoke方法恢复流程（新版LangGraph的正确方式）
    final_result = app.invoke(resume_inputs, config)

    print("\n=== 最终结果 ===")
    for msg in final_result["messages"]:
        print(msg.content)


if __name__ == '__main__':
    run_demo()