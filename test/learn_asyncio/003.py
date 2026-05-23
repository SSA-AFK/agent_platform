import re
import logging
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException, status
import aiofiles

# 1. 配置日志记录 (生产环境必备)
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

# ================= 生产环境常量配置 =================
# 允许的文件扩展名白名单 (必须小写)
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".md", ".docx"}
# 最大文件大小限制 (例如 50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024
# 当前运行目录
CURRENT_DIR = Path(__file__).resolve().parent


# ================================================

@app.post("/upload/{thread_id}")
async def upload_file(thread_id: str, file: UploadFile = File(...)):
    """
    生产级文件上传接口
    """
    # ---------------- 阶段一：严格的输入校验 ----------------

    # 1. 校验 thread_id，防止路径穿越攻击（例如恶意传入 "../../../"）
    if not re.match(r"^[a-zA-Z0-9_-]+$", thread_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不合法的 thread_id 格式，仅允许字母、数字、下划线和连字符"
        )

    # 2. 校验文件对象是否存在
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未检测到上传的文件"
        )

    # 3. 安全提取文件名：丢弃客户端可能传来的所有路径信息，仅保留基础文件名
    safe_filename = Path(file.filename).name
    file_extension = Path(safe_filename).suffix.lower()

    # 4. 白名单校验：判断文件扩展名
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"不支持的文件格式。仅允许上传: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # ---------------- 阶段二：安全构建目录 ----------------

    upload_dir = CURRENT_DIR / "upload" / f"loading{thread_id}"

    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"[Thread {thread_id}] 无法创建上传目录 {upload_dir}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误：无法创建目录"
        )

    file_path = upload_dir / safe_filename # 保存文件的路径
    real_file_size = 0 # 实际文件大小

    # ---------------- 阶段三：异步分块写入与大小限制 ----------------

    try:
        # 使用 aiofiles 确保文件 I/O 也是纯异步的，不阻塞主线程
        async with aiofiles.open(file_path, "wb") as out_file:
            # 分块读取，每次读取 1MB (保护内存)
            while chunk := await file.read(1024 * 1024):
                real_file_size += len(chunk)

                # 防御恶意超大文件攻击：超出上限立即中止
                if real_file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"文件过大，最大允许大小为 {MAX_FILE_SIZE / (1024 * 1024):.0f}MB"
                    )

                await out_file.write(chunk)

    except HTTPException:
        # 抛出由大小限制引起的 HTTP 异常前，清理已经写入的半截残缺文件
        if file_path.exists():
            file_path.unlink()
        raise

    except Exception as e:
        # 捕获不可预料的 I/O 错误（如磁盘满）
        logger.error(f"[Thread {thread_id}] 保存文件 {safe_filename} 时发生错误: {str(e)}")
        if file_path.exists():
            file_path.unlink()  # 清理可能存在的损坏文件
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件保存失败，请稍后重试"
        )

    finally:
        # 【极其重要】无论上传成功还是失败，必须关闭 UploadFile 句柄并清理底层缓存
        await file.close()

    # ---------------- 阶段四：成功响应 ----------------
    logger.info(f"[Thread {thread_id}] 文件 {safe_filename} 上传成功，大小: {real_file_size} Bytes")

    return {
        "code": 200,
        "message": "success",
        "data": {
            "thread_id": thread_id,
            "filename": safe_filename,
            "size_bytes": real_file_size,
            "save_path": str(file_path)
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)