from typing import Optional
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from backed.crud.db_config import ASYNC_DATABASE_URL

# 将 ASYNC_DATABASE_URL (postgresql+asyncpg://...) 转换为 psycopg 支持的格式 (postgresql://...)
PSYCOPG_URL = ASYNC_DATABASE_URL.replace("+asyncpg", "")

# 全局的 AsyncPostgresSaver 检查点，确保持久化记忆
global_memory_saver: Optional[AsyncPostgresSaver] = None
global_pool: Optional[AsyncConnectionPool] = None


async def init_checkpointer():
    global global_memory_saver, global_pool
    global_pool = AsyncConnectionPool(
        conninfo=PSYCOPG_URL,
        max_size=20,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": None
        },
        open=False
    )
    await global_pool.open()
    global_memory_saver = AsyncPostgresSaver(global_pool)
    # 初始化表结构（如果不存在）
    await global_memory_saver.setup()


async def close_checkpointer():
    global global_pool
    if global_pool:
        await global_pool.close()
