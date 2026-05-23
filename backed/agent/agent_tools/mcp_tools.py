import os
import httpx
from typing import Optional
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

AMAP_KEY = os.getenv("AMAP_MAPS_API_KEY", "93bb2fb496265e8fbd1a9e53307bd2a5")
AMAP_BASE_URL = "https://restapi.amap.com/v3"


@tool
def maps_geo(address: str, city: str = "") -> str:
    """
    地理编码工具：将地址转换为经纬度坐标
    适用于：需要将中文地址转换为GPS坐标的场景

    Args:
        address: 地址名称，如"北京海淀区中关村"
        city: 城市名称，如"北京"（可选，提高准确性）

    Returns:
        JSON格式的地理编码结果，包含经纬度信息
    """
    url = f"{AMAP_BASE_URL}/geocode/geo"
    params = {
        "key": AMAP_KEY,
        "address": address,
        "city": city,
        "output": "json"
    }

    try:
        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=10)
            data = response.json()

            if data.get("status") == "1" and data.get("geocodes"):
                geocode = data["geocodes"][0]
                location = geocode.get("location", "")
                formatted_address = geocode.get("formatted_address", "")
                return f"地址: {formatted_address}\n坐标: {location}"
            else:
                return f"未找到地址 '{address}' 的地理编码信息"
    except Exception as e:
        return f"地理编码查询失败: {str(e)}"


@tool
def maps_regeocode(location: str) -> str:
    """
    逆地理编码工具：将经纬度坐标转换为地址
    适用于：需要将GPS坐标转换为中文地址的场景

    Args:
        location: 经纬度坐标，格式为"经度,纬度"，如"116.397428,39.90923"

    Returns:
        JSON格式的逆地理编码结果，包含详细地址信息
    """
    url = f"{AMAP_BASE_URL}/geocode/regeo"
    params = {
        "key": AMAP_KEY,
        "location": location,
        "output": "json"
    }

    try:
        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=10)
            data = response.json()

            if data.get("status") == "1" and data.get("regeocode"):
                regeocode = data["regeocode"]
                formatted_address = regeocode.get("formatted_address", "")
                return f"坐标 {location} 对应的地址: {formatted_address}"
            else:
                return f"未找到坐标 '{location}' 的地址信息"
    except Exception as e:
        return f"逆地理编码查询失败: {str(e)}"


@tool
def maps_text_search(keywords: str, city: str = "", types: str = "") -> str:
    """
    地点搜索工具：搜索特定类型的地点
    适用于：查找餐厅、酒店、景点等POI信息

    Args:
        keywords: 搜索关键词，如"咖啡店"、"医院"
        city: 城市名称，如"北京"（可选）
        types: POI类型代码，如"餐饮服务"、"住宿服务"（可选）

    Returns:
        JSON格式的搜索结果，包含地点名称、地址、电话等信息
    """
    url = f"{AMAP_BASE_URL}/place/text"
    params = {
        "key": AMAP_KEY,
        "keywords": keywords,
        "city": city,
        "types": types,
        "output": "json",
        "page_size": 10
    }

    try:
        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=10)
            data = response.json()

            if data.get("status") == "1" and data.get("pois"):
                pois = data["pois"][:5]
                results = []
                for poi in pois:
                    name = poi.get("name", "")
                    address = poi.get("address", "")
                    tel = poi.get("tel", "无电话")
                    results.append(f"名称: {name}\n地址: {address}\n电话: {tel}")
                return "\n\n".join(results)
            else:
                return f"未找到 '{keywords}' 相关的地点"
    except Exception as e:
        return f"地点搜索失败: {str(e)}"


@tool
def maps_around_search(location: str, keywords: str, radius: int = 1000) -> str:
    """
    周边搜索工具：搜索指定位置周边的地点
    适用于：查找附近的餐厅、加油站、停车场等

    Args:
        location: 中心点坐标，格式为"经度,纬度"
        keywords: 搜索关键词，如"餐厅"、"加油站"
        radius: 搜索半径（米），默认1000米

    Returns:
        JSON格式的周边搜索结果
    """
    url = f"{AMAP_BASE_URL}/place/around"
    params = {
        "key": AMAP_KEY,
        "location": location,
        "keywords": keywords,
        "radius": radius,
        "output": "json",
        "page_size": 10
    }

    try:
        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=10)
            data = response.json()

            if data.get("status") == "1" and data.get("pois"):
                pois = data["pois"][:5]
                results = []
                for poi in pois:
                    name = poi.get("name", "")
                    address = poi.get("address", "")
                    distance = poi.get("distance", "未知")
                    results.append(f"名称: {name}\n地址: {address}\n距离: {distance}米")
                return "\n\n".join(results)
            else:
                return f"在周边未找到 '{keywords}'"
    except Exception as e:
        return f"周边搜索失败: {str(e)}"


@tool
def maps_direction_driving(origin: str, destination: str) -> str:
    """
    驾车路线规划工具：获取两点间的驾车路线
    适用于：规划自驾出行方案

    Args:
        origin: 起点坐标或地址，格式为"经度,纬度"或地址名称
        destination: 终点坐标或地址，格式为"经度,纬度"或地址名称

    Returns:
        JSON格式的驾车路线信息，包含距离、时间、路径详情
    """
    url = f"{AMAP_BASE_URL}/direction/driving"
    params = {
        "key": AMAP_KEY,
        "origin": origin,
        "destination": destination,
        "output": "json"
    }

    try:
        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=10)
            data = response.json()

            if data.get("status") == "1" and data.get("route"):
                route = data["route"]
                paths = route.get("paths", [])
                if paths:
                    path = paths[0]
                    distance = path.get("distance", "0")
                    duration = path.get("duration", "0")
                    distance_km = float(distance) / 1000
                    duration_min = int(duration) / 60

                    steps = path.get("steps", [])
                    step_details = []
                    for step in steps[:5]:
                        instruction = step.get("instruction", "")
                        step_details.append(instruction)

                    result = f"驾车路线规划:\n"
                    result += f"总距离: {distance_km:.2f}公里\n"
                    result += f"预计时间: {duration_min:.0f}分钟\n"
                    result += f"\n主要路段:\n"
                    result += "\n".join(step_details)
                    return result
                else:
                    return "未找到驾车路线"
            else:
                return f"驾车路线规划失败: {data.get('info', '未知错误')}"
    except Exception as e:
        return f"驾车路线规划失败: {str(e)}"


@tool
def maps_direction_transit_integrated(origin: str, destination: str, city: str = "") -> str:
    """
    公共交通路线规划工具：获取两点间的公交/地铁路线
    适用于：规划公共交通出行方案

    Args:
        origin: 起点坐标或地址
        destination: 终点坐标或地址
        city: 城市名称，如"北京"（必填，提高准确性）

    Returns:
        JSON格式的公共交通路线信息，包含换乘方案、时间、费用
    """
    url = f"{AMAP_BASE_URL}/direction/transit/integrated"
    params = {
        "key": AMAP_KEY,
        "origin": origin,
        "destination": destination,
        "city": city,
        "output": "json"
    }

    try:
        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=10)
            data = response.json()

            if data.get("status") == "1" and data.get("route"):
                route = data["route"]
                transits = route.get("transits", [])
                if transits:
                    transit = transits[0]
                    distance = transit.get("distance", "0")
                    duration = transit.get("duration", "0")
                    cost = transit.get("cost", "未知")
                    distance_km = float(distance) / 1000
                    duration_min = int(duration) / 60

                    segments = transit.get("segments", [])
                    route_details = []
                    for segment in segments:
                        if "bus" in segment:
                            bus_info = segment["bus"]
                            bus_lines = bus_info.get("buslines", [])
                            for line in bus_lines:
                                line_name = line.get("name", "")
                                departure = line.get("departure_stop", {}).get("name", "")
                                arrival = line.get("arrival_stop", {}).get("name", "")
                                route_details.append(f"乘坐 {line_name}: {departure} → {arrival}")
                        elif "railway" in segment:
                            railway = segment["railway"]
                            line_name = railway.get("name", "")
                            departure = railway.get("departurestop", {}).get("name", "")
                            arrival = railway.get("arrivalstop", {}).get("name", "")
                            route_details.append(f"乘坐地铁 {line_name}: {departure} → {arrival}")

                    result = f"公共交通路线规划:\n"
                    result += f"总距离: {distance_km:.2f}公里\n"
                    result += f"预计时间: {duration_min:.0f}分钟\n"
                    result += f"预估费用: {cost}元\n"
                    result += f"\n换乘方案:\n"
                    result += "\n".join(route_details)
                    return result
                else:
                    return "未找到公共交通路线"
            else:
                return f"公共交通路线规划失败: {data.get('info', '未知错误')}"
    except Exception as e:
        return f"公共交通路线规划失败: {str(e)}"


# 导出所有工具
amap_tools = [
    maps_geo,
    maps_regeocode,
    maps_text_search,
    maps_around_search,
    maps_direction_driving,
    maps_direction_transit_integrated
]

if __name__ == '__main__':
    print(amap_tools)


