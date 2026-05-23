from backed.agent.agent_tools.tavily_search import internet_search
from backed.agent.agent_tools.unsplash_tool import get_unsplash_image
from backed.agent.factory import chat_model

web_search_agent = {
    "name": "web_search_agent",
    "model": chat_model,
    "description": "用于搜索网页和获取图片",
    "system_prompt": "你是一个网络搜索与图片获取专家，可以使用搜索工具检索新闻、交通、经济等实时信息，也可以使用图片工具获取风景、美食等图片。当用户询问新闻资讯或需要图片展示时，选择合适的工具进行查询。**重要：你只能调用1次工具，获取结果后直接回答，不要再调用任何工具。**",
    "tools": [internet_search, get_unsplash_image],
}
