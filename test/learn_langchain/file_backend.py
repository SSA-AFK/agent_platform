from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from backed.agent.factory import chat_model

work_place = Path("work_place").resolve() #获取绝对路径

if not work_place.exists():
    work_place.mkdir(parents=True, exist_ok=True)

file_backend = FilesystemBackend(
    root_dir=work_place,
    virtual_mode=True,# 虚拟模式
)

llm = chat_model

main_agen = create_deep_agent(
    model=llm,
    tools=[],
    backend=file_backend, # 指定长期记忆类型
    system_prompt="你是一个智能助手，可以使用文件工具进行文件操作和读写！但是只有在用户明确要求的情况下，你才可以创建文件！！"
)

# 4. 运行并且验证
print("1：：： 不明确，看看会不会创建")
result_1 = main_agen.invoke(
    {
        "messages": [
            {"role": "user", "content": "帮我查询下python语言的介绍！！！"}
        ]
    }
)
print(f"最终结果{result_1['messages'][-1].content}")
print("2：：： 明确，看看会不会创建")

result_2 = main_agen.invoke(
    {
        "messages": [
            {"role": "user", "content": "帮我查询下java语言的介绍,并且帮我写到 java.txt文件中！！"}
        ]
    }
)
print(f"最终结果{result_2['messages'][-1].content}")



