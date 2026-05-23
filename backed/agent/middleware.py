from typing import Callable, Any, Awaitable
from langchain.agents import AgentState
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from langchain.agents.middleware import AgentMiddleware
from backed.utils.logger import logger


class LogBeforeModelMiddleware(AgentMiddleware):
    """模型调用前的日志中间件"""

    def before_model(self, state: AgentState, runtime: Runtime, **kwargs):
        msg_count = len(state.get("messages", []))
        logger.info(f"[before_model]即将调用模型，带有{msg_count}条消息。")
        logger.debug(f"[before_model]最后一条消息类型: {type(state['messages'][-1]).__name__}")
        return state


class MonitorToolMiddleware(AgentMiddleware):
    """工具调用监控中间件 - 支持同步和异步"""

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable
    ) -> ToolMessage | Command:
        """同步版本的工具调用包装"""
        tool_name = request.tool_call.get('name', 'unknown')
        tool_args = request.tool_call.get('args', {})

        logger.info(f"[tool sync]执行工具：{tool_name}")
        logger.info(f"[tool sync]传入参数：{tool_args}")

        try:
            result = handler(request)
            logger.info(f"[tool sync]{tool_name}执行完成")
            return result
        except Exception as e:
            logger.error(f"[tool sync]{tool_name}执行失败: {e}")
            return ToolMessage(
                content=f"工具执行失败: {str(e)}",
                tool_call_id=request.tool_call.get('id', '')
            )

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]]
    ) -> ToolMessage | Command:
        """异步版本的工具调用包装"""
        tool_name = request.tool_call.get('name', 'unknown')
        tool_args = request.tool_call.get('args', {})

        logger.info(f"[tool async]执行工具：{tool_name}")
        logger.info(f"[tool async]传入参数：{tool_args}")

        try:
            result = await handler(request)
            logger.info(f"[tool async]{tool_name}执行完成")
            return result
        except Exception as e:
            logger.error(f"[tool async]{tool_name}执行失败: {e}")
            return ToolMessage(
                content=f"工具执行失败: {str(e)}",
                tool_call_id=request.tool_call.get('id', '')
            )


# 注册中间件
middleware = [
    MonitorToolMiddleware(),
    LogBeforeModelMiddleware(),
]
