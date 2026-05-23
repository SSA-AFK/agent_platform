import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

PG_CONN_STRING = "postgresql://postgres:04017736@localhost:5432/agent?sslmode=disable"



async def show_chat_history():
    async with AsyncPostgresSaver.from_conn_string(PG_CONN_STRING) as saver:
        # 获取最新的检查点
        checkpoint_tuple = await saver.aget_tuple({
            "configurable": {"thread_id": "memory_test_fixed_123"}
        })

        if checkpoint_tuple:
            # 修正属性访问
            print("✅ 找到检查点:", str(checkpoint_tuple.checkpoint)[:8])  # 使用 checkpoint 属性
            state = checkpoint_tuple.checkpoint
            messages = state.get("channel_values", {}).get("messages", [])

            print(f"找到 {len(messages)} 条消息:")
            for i, msg in enumerate(messages):
                print(f"{i+1}. {msg}")
        else:
            print("未找到聊天记录")




if __name__ == "__main__":
    asyncio.run(show_chat_history())