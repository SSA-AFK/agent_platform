import json
from test.learn_langchain.my_mcp_server import mcp

class MCPWeatherClient:
    """MCP 天气服务客户端，用于访问 MCPWeatherServer 服务端"""

    def __init__(self, mcp_instance):
        self.mcp_instance = mcp_instance
        self.available_tools = mcp_instance._tools  # 获取服务端已注册的所有工具

    def check_tool_availability(self, tool_name: str) -> bool:
        """检查指定工具是否在服务端已注册"""
        is_available = tool_name in self.available_tools
        if is_available:
            print(f"工具 '{tool_name}' 已在服务端注册")
        else:
            print(f"工具 '{tool_name}' 未在服务端注册")
        return is_available

    def call_get_weather(self, city: str) -> str or None:
        """调用服务端的 get_weather 工具，查询指定城市天气"""
        tool_name = "get_weather"
        if not self.check_tool_availability(tool_name):
            return None

        try:
            # 调用服务端已注册的工具函数
            weather_result = self.available_tools[tool_name](city)
            print(f"查询结果：{weather_result}")
            return weather_result
        except Exception as exc:
            print(f"调用工具 '{tool_name}' 时发生错误：{exc}")
            return None


def run_client_demo():
    """客户端演示程序"""
    # 1. 初始化客户端（传入服务端的 mcp 实例）
    client = MCPWeatherClient(mcp)

    # 2. 调用天气查询工具（支持 Beijing、Shanghai、Guangzhou 等英文城市名）
    target_cities = ["Beijing", "Shanghai"]
    for city in target_cities:
        print(f"查询城市：{city}")
        weather_data = client.call_get_weather(city)
        if weather_data:
            # 格式化输出结果（可选，方便阅读）
            formatted_data = json.dumps(json.loads(weather_data), indent=4, ensure_ascii=False)
            print(f"格式化天气结果：\n{formatted_data}")
        print("-" * 50)


if __name__ == "__main__":
    # 确保服务端已启动（服务端进程需先运行，客户端才能正常导入 mcp 实例）
    run_client_demo()