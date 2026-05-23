import asyncio
import logging
import os
import random
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from langchain.tools import tool
import httpx  # 使用异步HTTP客户端
from tavily import TavilyClient
from backed.utils.logger import logger

load_dotenv()

# 从环境变量获取 API Key
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

@tool(description="查询天气的工具，location参数请使用【拼音城市名,国家码】格式，例如：Beijing,CN（北京）、New York,US（纽约）")
async def get_weather(location: str, units: str = "metric") -> str:
    """查询某个地方的当前天气。location 可以是 城市名 或 城市名,国家码"""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        logging.log(logging.ERROR, "未设置 OPENWEATHER_API_KEY 环境变量")
        return "错误：未设置 OPENWEATHER_API_KEY 环境变量"

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": location,
        "appid": api_key,
        "units": units,
        "lang": "zh_cn"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=8)
            r = response.json()

        if r.get("cod") != 200:
            logging.log(logging.WARNING, f"查询天气失败：{r.get('message', '城市未找到')}")
            return f"错误：{r.get('message', '城市未找到')}"

        w = r["weather"][0]
        m = r["main"]
        return (
            f"{r['name']} ({r.get('sys', {}).get('country', '')}) 当前天气：\n"
            f"状况：{w['description']}\n"
            f"温度：{m['temp']}°C  (体感 {m['feels_like']}°C)\n"
            f"湿度：{m['humidity']}%\n"
            f"风速：{r['wind']['speed']} m/s"
        )
    except Exception as e:
        logging.log(logging.ERROR, f"查询天气失败：{str(e)}")
        return f"查询失败：{str(e)}"

@tool(description="使用Tavily API进行高级网络搜索。")
async def search_with_tavily(query: str, mcp_url: Optional[str] = None) -> str:
    """
    使用Tavily API进行高级网络搜索，返回格式化结果。
    """
    try:
        result = tavily_client.search(
            query=query.strip(),
            max_results=10,
            search_depth="advanced",
            include_answer=True,
            include_images=False,
            max_images=0
        )

        output = []
        if result.get("answer"):
            output.append(f"🔍 **智能摘要**:\n{result['answer'][:800]}...")

        results = result.get("results", [])[:5]
        for i, item in enumerate(results, 1):
            title = item.get("title", "无标题")[:100]
            url = item.get("url", "")
            content = item.get("content", "")[:300]
            output.append(f"\n{i}. **{title}**\n   📎 {url}\n   💡 {content}...")

        formatted_result = "\n".join(output)
        return formatted_result or "未找到相关结果"

    except Exception as e:
        logger.error(f"Tavily搜索失败: {e}")
        return f"❌ 搜索服务暂不可用: {str(e)[:100]}。请稍后重试。"

@tool(description="获取用户所在城市的名称，以纯字符串形式返回")
async def get_user_location() -> str:
    # 模拟异步操作
    await asyncio.sleep(0.1)  # 模拟网络延迟
    return random.choice(["深圳", "合肥", "杭州"])

@tool(description="获取当前时间，格式为 YYYY-MM-DD HH:MM:SS")
async def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def main():
    result = await search_with_tavily("深圳的美食")
    print(result)

if __name__ == '__main__':
    asyncio.run(main())





