import requests
import os
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

@tool
def get_unsplash_image(query: str, orientation: str = "landscape", count: int = 1) -> str:
    """根据关键词从 Unsplash 搜索图片并返回图片 URL。
    参数:
        query: 搜索关键词(需要转为英文)
    """

    api_key = os.getenv("UNSPLASH_ACCESS_KEY")

    if not api_key:
        return "❌ 未配置 UNSPLASH_ACCESS_KEY 环境变量。"

    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": count,
        "client_id": api_key  # 只保留官方支持的参数
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = data.get('results', [])
        if results:
            img_url = results[0]['urls']['regular']
            desc = results[0].get('description') or results[0].get('alt_description', '无描述')
            author = results[0]['user']['name']
            return f"✅ 找到图片：\nURL: {img_url}\n描述: {desc}\n摄影师: {author}"
        return f"❌ 未找到与 '{query}' 相关的图片。"

    except requests.exceptions.HTTPError as e:
        status_code = response.status_code
        if status_code == 401:
            return "❌ 密钥错误"
        elif status_code == 403:
            return "❌ 每小时请求次数超限（免费版50次/小时）"
        elif status_code == 400:
            return "❌ 请求参数错误"
        else:
            return f"❌ HTTP 错误 {status_code}: {str(e)}"
    except Exception as e:
        return f"❌ 出错：{str(e)}"

if __name__ == '__main__':
    print(get_unsplash_image.invoke("Paris"))