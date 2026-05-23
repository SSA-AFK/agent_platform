from langchain.chat_models import init_chat_model
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
import redis  #导入原生redis库，pip install redis==5.3.1
from backed.agent.factory import chat_model
REDIS_URL = "redis://localhost:6379"
# 创建原生Redis客户端,decode_responses 控制 Redis 返回数据的类型：False 返字节串，True 返字符串
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# 设置本地模型
llm = chat_model

# 创建提示模板
prompt = ChatPromptTemplate.from_messages([
    MessagesPlaceholder("history"),
    ("human", "{question}")
])

def get_session_history(session_id: str) -> RedisChatMessageHistory:
    """获取或创建会话历史（使用 Redis）"""
    # 创建 Redis 历史对象
    history = RedisChatMessageHistory(
        session_id=session_id,
        url=REDIS_URL,
        # ttl=3600  # 注释：关闭自动过期，避免重启后数据被清理
    )

    return history

# 创建带历史的链
chain = RunnableWithMessageHistory(
    prompt | llm,
    get_session_history,
    input_messages_key="question",
    history_messages_key="history"
)

# 配置
# session_id 就是登录大模型的各自帐户，类似登录手机号码，各不相同
config = RunnableConfig(configurable={"session_id": "user-001"})

# 主循环
print("开始对话（输入 'quit' 退出）")
while True:
    question = input("\n输入问题：")
    if question.lower() in ['quit', 'exit', 'q']:
        break

    response = chain.invoke({"question": question}, config)
    print(f"AI: {response}")
    # 等同于redis-cli的SAVE命令，强制写入dump.rdb
    redis_client.save()