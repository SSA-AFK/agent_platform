# -*- coding: utf-8 -*-
"""
DeepAgents 中断审批机制示例
核心功能：演示高危工具调用前的人工审批流程，支持删除数据库表/文件的审批控制
"""
from langchain.tools import tool
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver  # 内存检查点，用于保存中断状态
from langgraph.types import Command  # 恢复执行的指令类型

from backed.agent.factory import chat_model


llm = chat_model

# 删除表工具
@tool
def delete_database(table_name: str):
    """
    高危动作工具，删除传入的表！
    :param table_name: 要删除的表名
    :return: 操作的返回结果
    """
    print(f"调用了delete_database工具。删除了{table_name}表！！")
    return f"删除了表{table_name}！"

# 删除文件工具
@tool
def delete_file(file_name: str):
    """
    高危动作工具，删除传入的文件！
    :param file_name: 要删除的文件名
    :return: 操作的返回结果
    """
    print(f"调用了delete_file工具。删除了{file_name}文件！！")
    return f"删除了文件{file_name}！"

# 查询表数据工具
@tool
def select_database(table_name: str):
    """
    查询动作工具，查询传入的表数据！
    :param table_name: 要查询的表名
    :return: 查询结果
    """
    print(f"调用了select_database工具。查询了{table_name}表数据！！")
    return f"查询了表{table_name}的数据！"


# 创建deepagent，同时给高危工具设置人机交互！ 拦截动作！
# 1. 必备内容 短期记忆 + 线程id
checkpointer = InMemorySaver()
thread_config = {
    "configurable" :{"thread_id":"erdaye"}
}

# 2.常见deepagent，设置高危工具需要拦截处理
main_agent = create_deep_agent(
    model=llm,
    tools=[delete_database, delete_file, select_database],
    checkpointer=checkpointer,  # 必须的记录过程
    system_prompt="回答使用中文，调用对应的工具实现对应的功能！",
    interrupt_on={
        "delete_database": True, # 通过 编辑 或者拒绝 ,
        "delete_file": True, # 通过 编辑 或者拒绝 ,  {"allowed_decisions": ["approve", "reject"]}
        "select_database": False
    }
)

# 3. 预执行，本次不会真正的执行！ 所有都不会执行，判定本次执行链中是否存在 人机交互节点！ 存在需要设置后 二次执行！
result_1 = main_agent.invoke({
    "messages":[
        {"role":"user","content":"先查询product表的数据！再删除user表，最后，删除zhaoweifeng.txt文件"}
    ]
},config=thread_config) # 记录人 继续工作

# 4. 检查本次执行是否存在人机交互动作  规定： 有人机交互动作，会将交互的拦截点信息存储到  __interrupt__
interrupt = result_1['__interrupt__']
"""
[ -&gt; 列表
  Interrupt -&gt; 对象 
     (value  -&gt;  value 属性
          存储拦截信息 -&gt; 字典 {
               'action_requests': -&gt; 列表，存储了本次触发的拦截的工具信息（名字和参数） [
                                  {'name': 'delete_database', 'args': {'table_name': 'user'}, 'description': "To"}, 
                                  {'name': 'delete_file', 'args': {'file_name': 'zhaoweifeng.txt'}, 'description': "T}"}], 
              'review_configs': [ -&gt; 触发拦截工具以后，拦截工具有的后续动作有哪些？
                                 {'action_name': 'delete_database', 'allowed_decisions': ['approve', 'edit', 'reject']}, 
                                 {'action_name': 'delete_file', 'allowed_decisions': ['approve', 'edit', 'reject']}]}, id='efc9a550c63c45bfdb429bf79f6215a6')]
"""
#print(interrupt)

if interrupt:
   # 处理人机交互动作，二次执行
   # 输出一共有几个工具被拦截了， 这些工具的名字是什么！！！
   action_requests = interrupt[0].value['action_requests']
   print(f"本次需要审核的工具数量：{len(action_requests)} ,具体拦截的工具：{[action['name'] for action in action_requests]}")

   # 审批意见
   decisions = []
   for action in action_requests:
       #   'name': 'delete_database', 'args': {'table_name': 'user'}, 'description': "To"},
       action_name = action['name']
       action_args = action['args']
       # 检查代码，放行 还是 拦截 还是 编辑
       if action_name == "delete_database":
           # 1. 给前端推送 信息 获得审批意见
           # 2. 前端接收信息 -》 人页面点点点 输入
           # 3. 接收前端返回结果，走逻辑，放行，还是拦截 还是编辑
           # 拦截
           # 每一次的拦截动作 {type: "reject | approve"}
           # 按照 decisions 元素顺序，进行拦截还还是放行
           # decisions.append({"type":"reject"})
           # 不拒绝，但是我编辑下参数！ edit -&gt; 放行 -&gt; 修改参数
           decisions.append({
               "type":"edit",
               "edited_action":{
                   # name -》 工具名
                   "name":action_name,
                   # args : { 修改的参数  key -&gt; 参数名  value - &gt; 修改的新的参数值 }
                   "args":{
                       "table_name":"hahahahahahahaherdaye"
                   }
               }
           })

       elif action_name == "delete_file":
           # 放行
           decisions.append({"type": "approve"})


   result_2 = main_agent.invoke(
      # 审批意见 传入审批意见，再次执行！！
      Command(
          resume={
              "decisions":decisions
          }
      ),
      config=thread_config
   )

   print(f"最终结果{result_2['messages'][-1].content}")
