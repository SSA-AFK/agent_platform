from deepagents import create_deep_agent, CompiledSubAgent
from langchain_core.tools import tool
from backed.agent.factory import chat_model

model = chat_model

@tool
def calculate(expression: str) -> str:
    """计算数学表达式，例如 '3333+48+52'。"""
    try:
        return str(eval(expression))
    except:
        return "计算错误"

# 方法1：字典配置（最简单，无需 create_agent）
main_agent = create_deep_agent(
    model=model,
    system_prompt="""你是一个智能助手，你叫小智。数学运算调用工具。""",
    tools= [calculate],
)


stream = main_agent.stream({
    "messages": [
        {"role": "user", "content": "计算3733+48+52"},
    ],
})
for chunk in stream:
    for node_name,state in chunk.items():
        if state is None or "messages"  not in state:
            continue
        messages = state["messages"]

        if messages and isinstance(messages, list):
            last_massage = messages[-1]
            if node_name == "model":
                if last_massage.tool_calls:
                    for tool_call in last_massage.tool_calls:
                        if tool_call["name"] =='task':
                            print(f"【model】决定调用子智能体{tool_call['args']['subagent_type']},参数为：{tool_call['args']}")
                        else:
                            print(f"【model】决定调用子工具{tool_call['name']}")
                elif last_massage.content:
                    print(f"【model】: {last_massage.content}")
            elif node_name == "tools":
                    name = last_massage.name
                    content = last_massage.content
                    print(f"【agent】调用了具体的工具{name},返回结果为：{content[:100] + '...'}")
