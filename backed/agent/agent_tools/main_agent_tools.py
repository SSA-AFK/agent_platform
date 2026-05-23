import datetime
import random
from langchain.tools import tool

@tool(description="获取用户所在城市的名称，以纯字符串形式返回")
def get_user_location() -> str:
    # 模拟异步操作

    return random.choice(["深圳", "合肥", "杭州", "上海", "广州", "苏州", "无锡", "南京", "西安", "武汉", "成都", "郑州", "天津", "重庆", "青岛", "济南", "厦门", "烟台", "珠海", "佛山", "东莞", "石家庄", "太原", "昆明", "杭州", "合肥", "武汉", "西安", "南京", "上海", "广州", "深圳", "苏州", "无锡",])


@tool
def get_current_time() -> str:
    """
    获取当前时间
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if __name__ == '__main__':
    print(get_user_location.invoke(""))
    print(get_current_time.invoke(""))