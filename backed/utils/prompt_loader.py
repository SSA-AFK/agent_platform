from backed.utils.path_tool import get_abs_path

def load_system_prompts():
    prompt_path = get_abs_path("prompts/system_prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 如果文件不存在，返回默认提示词
        return """你是专业智能客服，请用专业的知识回答用户问题。"""

def load_context_prompt():
    prompt_path = get_abs_path("prompts/context_prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # 如果文件不存在，返回默认提示词
        return """压缩历史对话，根据上下文，回答用户问题。"""


