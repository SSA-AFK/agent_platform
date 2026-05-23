from pathlib import Path

def get_project_root():
    """向上查找直到找到项目标志文件"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "backed").exists() or (parent / ".git").exists():
            return parent
    raise RuntimeError("无法找到项目根目录")


PROJECT_ROOT = get_project_root()

current_dir = Path(__file__).resolve().parent

print(f"项目根目录: {PROJECT_ROOT}")
print(f"当前目录: {current_dir}")

thread_id = 66

upload_dir = current_dir / "upload"/ f"loading{thread_id}"
upload_dir.mkdir(parents=True, exist_ok=True)

if upload_dir.exists():
    print(f"上传目录已存在: {upload_dir}")
else:
    print(f"创建上传目录: {upload_dir}")

chatting =" current_dir \\ chatting"
print(chatting.replace("\\", "/"))

