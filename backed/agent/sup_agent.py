import uuid

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from backed.agent.factory import chat_model
from backed.agent.sub_agent.route_agent import route_agent
from backed.agent.sub_agent.weather_agent import weather_agent
from backed.agent.sub_agent.web_search_agent import web_search_agent
from backed.agent.checkpointer import global_memory_saver

main_agent = create_deep_agent(
        model=chat_model,
        checkpointer=global_memory_saver,
        system_prompt="""
你是智能旅游规划助手，根据用户查询委托给子代理：

- **天气相关**（如"南京天气"、"今天温度"）→ 委托给 weather_agent
- **新闻/搜索/图片相关**（如"南京新闻"、"最新事件"、"经济数据"、"某某风景图片"）→ 委托给 web_search_agent
- **旅游规划**（如"从北京到天津南"、"推荐景点"）→ 委托给 route_agent
- 其他问题直接回答

使用子代理获取实时数据，不要凭记忆回答新闻/天气/地图。

**重要指示：** 当你需要委托给子代理时，必须使用 `task` 工具，并且**必须提供以下两个参数**：
1. `description`: (必需) 详细描述子代理需要完成的任务。
2. `subagent_type`: (必需) 子代理的名称（如 "weather_agent"）。
**绝对禁止**调用没有参数的 `task` 工具。例如，如果你想查天气，请严格按照以下格式提供参数：
`{"description": "查询南京今天的天气情况", "subagent_type": "weather_agent"}`
        """,
        subagents=[weather_agent, web_search_agent, route_agent]
    )

session_id = uuid.uuid4()

config = {
    "configurable": {
        "thread_id": session_id
    }
}

def test_steam(query):
    """
    使用mainagent执行传入的问题
    :param query:
    :return:
    """
    stream = main_agent.stream({
        "messages":[
            {"role":"user", "content":query}
        ]
    }, config=config)

    for chunk in stream:
        # chunk -&gt; {"model / tools " : {"messages":[{},{},{}]}}
        # model   |  {messages : []}
        for node_name , state in chunk.items():
            # 如果state是None,或者state没有messages我们就跳过！！
            if state is None or "messages" not in state: continue
            # 获取messages数据
            messages = state["messages"]
            if messages and isinstance(messages, list):
                last_msg = messages[-1]
                # 决定如何处理  node_name = model 1. 大模型决定调用工具 2.大模型决定调用子agent 3.大模型返回结果了
                # || node_name = tools  调用自己的工具，并获取返回结果
                if node_name == "model":
                    # model = &gt; 返回的结果 =》 决定调用哪些
                    if last_msg.tool_calls:
                        # 决定调用子工具或者subAgent
                        for tool_call in last_msg.tool_calls:
                            if tool_call['name'] == 'task':
                                # 决定调用某个subAgent
                                print(f"【model】决定调用子智能体{tool_call['args']['subagent_type']}")
                            else:
                                # 决定调用某个工具
                                print(f"【model】决定调用子工具{tool_call['name']},传入的参数为：{tool_call['args']}")
                    elif last_msg.content:
                        # 模型返回最终结果
                        print(f"【model】返回最终结果：{last_msg.content}")
                elif node_name == "tools":
                    # agent = &gt; 调用自己的工具了，并获取了结果
                    name = last_msg.name
                    content = last_msg.content
                    print(f"【agent】调用了具体的工具{name},返回结果为：{content[:100]+'...'}")

if __name__ == "__main__":
    tast1 = test_steam("我在北京今天天气怎么样")
    print(tast1)

