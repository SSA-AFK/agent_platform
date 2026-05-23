from langchain_core.tools import tool
import requests
import os

# 设置你的 OpenWeatherMap API key（推荐用环境变量）
API_KEY = os.getenv("OPENWEATHER_API_KEY")  # 例如：export OPENWEATHER_API_KEY="your_key_here"


@tool
def get_weather(city: str) -> str:
    """
    获取指定城市的当前天气信息。

    参数:
    city: 城市名称，例如 "Beijing" 或 "Shanghai"
    """
    if not API_KEY:
        return "错误：请设置 OPENWEATHER_API_KEY 环境变量"

    url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",  # 摄氏度
        "lang": "zh_cn"  # 中文描述
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        weather = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        feels_like = data["main"]["feels_like"]

        return f"{city} 当前天气：{weather}，温度 {temp}°C，体感 {feels_like}°C，湿度 {humidity}%"

    except requests.exceptions.RequestException as e:
        return f"获取 {city} 天气失败：{str(e)}"
    except KeyError:
        return f"未找到 {city} 的天气信息，请检查城市名称"