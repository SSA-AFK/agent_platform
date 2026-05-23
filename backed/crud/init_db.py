import asyncio
import os
import logging
import sys

# Windows平台事件循环策略设置（必须在其他导入之前）
if sys.platform == 'win32':
    from asyncio import WindowsSelectorEventLoopPolicy
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# ========== 核心配置 ==========
# 1. SQLAlchemy 异步 URL（用于 create_async_engine）
SQLALCHEMY_URL = os.getenv("DB_URL")
# 2. PostgreSQL 原生连接字符串（用于 AsyncPostgresSaver）
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "agent")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "04017736")

# 空值检查
if not SQLALCHEMY_URL:
    raise ValueError("❌ 未设置 DB_URL 环境变量，请检查 .env 文件")

# 构建 PostgreSQL 原生连接字符串
PG_CONN_STRING = (
    f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} "
    f"user={PG_USER} password={PG_PASSWORD}"
)
logger.info(f"🔧 PostgreSQL 原生连接字符串：{PG_CONN_STRING}")

# 创建异步 SQLAlchemy 引擎（修复：移除不兼容的 connect_timeout，改用 asyncpg 支持的参数）
async_engine = create_async_engine(
    SQLALCHEMY_URL,
    echo=False,
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    # 关键修复：asyncpg 用 timeout 而非 connect_timeout，且放在 connect_args 中
    connect_args={"timeout": 10}
)

# 创建异步会话工厂
AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 初始化数据库（最终稳定版）
async def init_db():
    """初始化 LangGraph PostgreSQL 检查点所需的表结构"""
    try:
        # 步骤1：初始化 LangGraph 检查点表（核心目标）
        async with AsyncPostgresSaver.from_conn_string(PG_CONN_STRING) as checkpointer:
            await checkpointer.setup()
            logger.info("✅ LangGraph 检查点表初始化完成")

        # 步骤2：验证 SQLAlchemy 连接（可选，增强版）
        try:
            async with async_engine.connect() as conn:
                await conn.execute("SELECT 1")
                logger.info("✅ SQLAlchemy 数据库连接验证成功")
        except Exception as e:
            logger.warning(f"⚠️ SQLAlchemy 连接验证警告：{str(e)}，但 LangGraph 检查点表已创建成功")

    except Exception as e:
        logger.error(f"❌ 数据库初始化失败：{str(e)}", exc_info=True)
        raise

# 安全关闭数据库引擎
async def close_db():
    """关闭数据库引擎，释放连接池"""
    try:
        await async_engine.dispose()
        logger.info("✅ 数据库引擎已关闭")
    except Exception as e:
        logger.warning(f"⚠️ 关闭数据库引擎警告：{str(e)}")

# 主函数
async def main():
    try:
        await init_db()
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())