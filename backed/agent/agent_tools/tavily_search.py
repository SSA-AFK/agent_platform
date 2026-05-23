# ======================== 导入核心依赖 ========================
import datetime
from typing import Literal
from langchain_core.tools import tool
from tavily import TavilyClient
import os
from dotenv import load_dotenv

# ======================== 初始化配置 ========================
load_dotenv()
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


@tool
def internet_search(
    query: str,
    search_depth: Literal["basic", "advanced"] = "basic",
    max_results: int = 5
) -> str:
    """
    联网实时搜索工具，用于获取最新、实时、外部网络信息
    适用场景：时事新闻、最新政策、实时数据、外部知识库查询、时效性内容

    Args:
        query: 搜索查询关键词/问题
        search_depth: 搜索深度，basic基础快速搜索，advanced深度详细搜索
        max_results: 返回最大搜索结果条数

    Returns:
        整合后的搜索结果文本
    """
    # 调用 Tavily 联网搜索
    response = tavily_client.search(
        query=query,
        search_depth=search_depth,
        max_results=max_results
    )

    # 格式化拼接结果
    result_list = []
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result_list.append(f"【当前搜索时间】：{current_time}\n")

    for idx, res in enumerate(response.get("results", []), 1):
        result_list.append(f"## 搜索结果{idx}")
        result_list.append(f"标题：{res.get('title', '')}")
        result_list.append(f"链接：{res.get('url', '')}")
        result_list.append(f"内容摘要：{res.get('content', '')}\n")

    return "\n".join(result_list)



if __name__ == "__main__":
    res = internet_search.invoke({"query": "南京本地新闻", "topic": "news"})
    print(res)