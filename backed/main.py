from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backed.routers.chat import chat_router
from backed.routers.users import user_router
from backed.agent.checkpointer import init_checkpointer, close_checkpointer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时初始化检查点
    await init_checkpointer()
    yield
    # 应用关闭时清理资源
    await close_checkpointer()

app = FastAPI(lifespan=lifespan)


app.include_router(user_router)
app.include_router(chat_router)
# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境中应设置为具体的域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头部
)

# 全局异常处理

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


if __name__ == "__main__":
    import uvicorn
    import asyncio
    import selectors
    import sys

    # 确保在 Windows 上使用 SelectorEventLoop
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()
        )
        # uvicorn.run 在内部会创建新的 event loop，我们需要告诉它使用 SelectorEventLoop
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, loop="asyncio")
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)