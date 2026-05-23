from backed.agent.factory import chat_model
from test.learn_langchain.my_mcp_server import get_weather

weather_agent = {
    "model":chat_model,
    "name": "weather_agent",
    "description": "用于获取天气信息",
    "system_prompt": "你是一个天气查询助手，负责获取和提供天气信息。当用户询问天气情况时，使用工具获取准确的天气数据并以友好的方式呈现，例如“Nanjing”。**重要：你只能调用1次工具，获取结果后直接回答，不要再调用任何工具。**",
    "tools": [get_weather],
}