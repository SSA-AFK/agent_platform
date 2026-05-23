import asyncio
import os
import uuid
import sys
from deepagents.middleware.filesystem import FilesystemMiddleware  # 添加这行
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver

if sys.platform == 'win32':
    from asyncio import WindowsSelectorEventLoopPolicy

    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

from backed.agent.agent_tools import get_weather, search_with_tavily, get_user_location, get_current_time
from backed.agent.factory import chat_model
from backed.agent.middleware import middleware
from backed.utils.logger import logger
from backed.utils.prompt_loader import load_system_prompts, load_context_prompt

load_dotenv()

PG_CONN_STRING = os.getenv(
    "PG_CONN_STRING",
    "postgresql://postgres:04017736@localhost:5432/agent?sslmode=disable"
)


class ReactAgent:
    def __init__(self, checkpointer=None):
        # 外部传入 checkpointer，不再内部初始化
        self.checkpointer = checkpointer or MemorySaver()
        self.agent = None
        self._thread_id = None

    async def initialize(self):
        # 创建 agent
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts() + "\n\n" + load_context_prompt(),
            tools=[get_weather, search_with_tavily, get_user_location, get_current_time],
            middleware=[FilesystemMiddleware(), *middleware],
            checkpointer=self.checkpointer
        )
        logger.info("✅ Agent 初始化成功")

    async def execute_stream(self, query: str, thread_id: str = None):
        if self.agent is None:
            await self.initialize()

        if not query:
            yield "查询不能为空！\n"
            return

        # 固定 thread_id
        if thread_id is None:
            if self._thread_id is None:
                self._thread_id = str(uuid.uuid4())
            thread_id = self._thread_id

        config = {"configurable": {"thread_id": thread_id}}
        input_dict = {"messages": [{"role": "user", "content": query}]}

        try:
            async for chunk in self.agent.astream(input_dict, config, stream_mode="values"):
                if "messages" in chunk:
                    latest = chunk["messages"][-1]
                    if isinstance(latest, AIMessage) and latest.content:
                        yield latest.content + "\n"
            logger.info(f"✅ 会话 {thread_id} 执行成功，状态已保存")
        except Exception as e:
            logger.error(f"❌ Agent执行失败：{e}")
            yield f"错误：{str(e)}\n"

    def set_thread_id(self, thread_id: str):
        self._thread_id = thread_id

    def get_thread_id(self) -> str:
        return self._thread_id or str(uuid.uuid4())


async def main():
    checkpointer = None

    try:
        async with AsyncPostgresSaver.from_conn_string(PG_CONN_STRING) as pg_checkpointer:
            await run_agent_tests(pg_checkpointer)
            return  # 成功使用 Postgres，直接返回
    except Exception as e:
        logger.warning(f"Postgres 连接失败，使用 MemorySaver: {e}")

    # 只有 Postgres 失败时才降级使用 MemorySaver
    await run_agent_tests(MemorySaver())


async def run_agent_tests(checkpointer):
    agent = ReactAgent(checkpointer=checkpointer)

    # 固定 thread_id 测试记忆
    test_thread_id = "memory_test_fixed_123"
    agent.set_thread_id(test_thread_id)
    print(f" 使用固定 thread_id: {test_thread_id}")

    print("🔄 测试总结触发")
    async for chunk in agent.execute_stream("现在对话很长了，请总结我们的对话到文件！"):
        print(chunk, end="", flush=True)


if __name__ == '__main__':
    asyncio.run(main())