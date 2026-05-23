import asyncio
import sys
from typing import Any, Dict

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# 数据库连接字符串
PG_CONN_STRING = "postgresql://postgres:04017736@localhost:5432/agent?sslmode=disable"

def extract_message_content(msg: Any) -> str:
    """提取消息的核心内容，兼容不同格式的消息对象"""
    # 如果是字典
    if isinstance(msg, dict):
        return msg.get("content", "无内容")
    # 如果是对象（如AIMessage/HumanMessage）
    elif hasattr(msg, "content"):
        return msg.content
    # 其他格式转为字符串
    else:
        return str(msg)

async def show_chat_history():
    async with AsyncPostgresSaver.from_conn_string(PG_CONN_STRING) as saver:
        # 获取指定thread_id的检查点
        checkpoint_tuple = await saver.aget_tuple({
            "configurable": {"thread_id": "memory_test_fixed_123"}
        })

        if checkpoint_tuple:
            print("✅ 找到检查点 (版本):", checkpoint_tuple.checkpoint.get("v", "未知"))
            state = checkpoint_tuple.checkpoint
            messages = state.get("channel_values", {}).get("messages", [])

            print(f"\n📝 共找到 {len(messages)} 条聊天记录：")
            print("-" * 50)
            # 格式化输出每条消息的核心内容
            for i, msg in enumerate(messages):
                content = extract_message_content(msg)
                # 区分用户/AI消息（简单判断，可根据实际场景调整）
                role = "用户" if i % 2 == 0 else "AI"
                print(f"{i+1}. [{role}] {content}")
            print("-" * 50)
        else:
            print("❌ 未找到该thread_id的聊天记录")

if __name__ == "__main__":
    asyncio.run(show_chat_history())