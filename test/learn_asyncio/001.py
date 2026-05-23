import asyncio
import time
import uuid
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backed.utils.path_tool import get_project_root, get_abs_path


async def work01():
    for i in range(5):
        print(f'[{time.time():.2f}] work01')
        await asyncio.sleep(1)
async def work02():
    for i in range(5):
        print(f'[{time.time():.2f}] work02')
        await asyncio.sleep(1)
async def main():
    # 创建任务
    task1 = asyncio.create_task(work01(), name='work01')
    task2 = asyncio.create_task(work02(), name='work02')
    # 等待任务完成
    await task1
    await task2
    
    # 测试路径工具
    print(f"项目根目录: {get_project_root()}")
    print(f"配置文件路径: {get_abs_path('backed/.env')}")

if __name__ == '__main__':
    asyncio.run(main())