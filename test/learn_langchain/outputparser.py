from langchain_core.output_parsers import StrOutputParser,JsonOutputParser,PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import  BaseModel,Field
from backed.agent.factory import chat_model

#
# class Person(BaseModel):
#     time: str = Field(description="时间")  #
#     person: str = Field(description="人物")
#     event: str = Field(description="事件")
#
# parser = JsonOutputParser(pydantic_object=Person)
#
# format_instructions = parser.get_format_instructions()
#
# # 创建聊天提示模板，定义系统角色和用户输入格式
# chat_prompt = ChatPromptTemplate.from_messages([
#     ("system", "你是一个AI助手，你只能输出结构化JSON数据。"),
#     ("human", "请生成一个关于{topic}的新闻。{format_instructions}")
# ])
#
# # 格式化提示词，填入具体主题和格式化指令
# prompt = chat_prompt.format_messages(topic="小米su7跑车", format_instructions=format_instructions)
#
#
model = chat_model
#
# result = model.invoke( prompt)


# # 使用解析器将模型输出解析为结构化数据
# response = parser.invoke(result)
#
# print(response)

from pydantic import BaseModel, Field
from typing import List

class Animal(BaseModel):
    animal: str = Field(description="动物名称")
    emoji: str = Field(description="动物表情")

class AnimalList(BaseModel):
    animals: List[Animal] = Field(description="动物列表")
messages = [{"role": "user", "content": "任意生成三种动物，以及他们的 emoji 表情"}]
llm_with_structured_output = model.with_structured_output(AnimalList)
resp = llm_with_structured_output.invoke(messages)
print(resp)
