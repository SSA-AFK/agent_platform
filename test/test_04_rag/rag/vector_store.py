import os
import asyncio
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from chromadb.config import Settings
from typing import List, Optional

from backed.agent.factory import chat_model, embed_model
from backed.utils.file_handler import txt_loader, pdf_loader, listdir_with_allowed_type, get_file_md5_hex
from backed.utils.logger import get_logger
from backed.utils.path_tool import get_abs_path

logger = get_logger(name="vector_store")



class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name="case",
            embedding_function=embed_model,
            persist_directory="./chroma_db",
            client_settings=Settings(persist_directory="./chroma_db")
        )
        self._all_documents = None  # 初始化全量文档缓存

        # 生产级中文最优切分策略
        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # 中文最优：1000 字
            chunk_overlap=200,  # 重叠 20%，保证上下文连贯
            separators=[
                "\n\n",  # 1. 先按段落切（最安全）
                "\n",  # 2. 再按换行
                "。", "！", "？",  # 3. 中文句子
                "；", "，",  # 4. 中文短语
                " ",  # 5. 空格
                ""  # 6. 最后兜底
            ],
            length_function=len,
        )

    async def get_all_documents(self) -> List[Document]:
        """获取全量文档（带缓存，避免重复加载）"""
        if self._all_documents is None:
            # 获取 Chroma 底层 collection
            collection = self.vector_store._collection
            results = await asyncio.to_thread(collection.get, include=["documents", "metadatas"])
            # 处理空值情况
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            # 确保documents和metadatas长度一致
            min_len = min(len(documents), len(metadatas))
            self._all_documents = [
                Document(page_content=documents[i], metadata=metadatas[i] if i < len(metadatas) else {})
                for i in range(min_len)
            ]
            logger.info(f"加载全量文档完成，共{len(self._all_documents)}条")
        return self._all_documents

    def get_retriever(self, k: int = 3):
        return self.vector_store.as_retriever(search_kwargs={"k": k})

    async def add_documents(self, documents: List[Document]):
        """添加文档到向量库"""
        try:
            await asyncio.to_thread(self.vector_store.add_documents, documents)
            logger.info(f"成功添加{len(documents)}个文档到向量库")
        except Exception as e:
            logger.error(f"添加文档异常：{str(e)}")

    async def similarity_search(self, query: str, k: int = 3):
        """相似性搜索"""
        try:
            retriever = self.get_retriever()
            return await asyncio.to_thread(retriever.invoke, query)
        except Exception as e:
            logger.error(f"相似性搜索异常：{str(e)}")
            return []

    async def load_document(self):
        """
        从数据文件夹内读取数据文件，转为向量存入向量库
        要计算文件的MD5做去重
        :return: None
        """

        def check_md5_hex(md5_for_check: str) -> bool:
            md5_file_path = get_abs_path("md5.text")
            # 确保MD5文件所在目录存在
            md5_dir = os.path.dirname(md5_file_path)
            os.makedirs(md5_dir, exist_ok=True)

            if not os.path.exists(md5_file_path):
                # 创建文件
                open(md5_file_path, "w", encoding="utf-8").close()
                return False  # md5 没处理过

            # 更快：一次性读入 set
            with open(md5_file_path, "r", encoding="utf-8") as f:
                existing_md5s = set(line.strip() for line in f if line.strip())
                return md5_for_check in existing_md5s

        def save_md5_hex(md5_for_check: str):
            md5_file_path = get_abs_path("md5.text")
            # 确保MD5文件所在目录存在
            md5_dir = os.path.dirname(md5_file_path)
            os.makedirs(md5_dir, exist_ok=True)

            with open(md5_file_path, "a", encoding="utf-8") as f:
                f.write(md5_for_check + "\n")

        def get_file_documents(read_path: str) -> List[Document]:
            """获取文件文档并补充元数据"""
            documents: List[Document] = []
            file_type = os.path.splitext(read_path)[1].lower()

            if read_path.endswith(".txt"):
                documents = txt_loader(read_path)
            elif read_path.endswith(".pdf"):
                documents = pdf_loader(read_path)

            # 补充元数据
            for doc in documents:
                doc.metadata.update({
                    "source": read_path,
                    "file_type": file_type,
                    "loader": "txt_loader" if file_type == ".txt" else "pdf_loader"
                })

            return documents

        # 优化文件后缀匹配，确保带点
        allowed_extensions = (".txt", ".pdf")
        allowed_files_path: List[str] = listdir_with_allowed_type(
            get_abs_path("data"),
            allowed_extensions,
        )

        for path in allowed_files_path:
            # 获取文件的MD5
            md5_hex = get_file_md5_hex(path)

            if check_md5_hex(md5_hex):
                logger.info(f"文件{path}已经处理过，跳过")
                continue

            try:
                documents: List[Document] = get_file_documents(path)

                if not documents:
                    logger.warning(f"文件{path}没有有效文本内容，跳过")
                    continue

                split_document: List[Document] = self.spliter.split_documents(documents)

                if not split_document:
                    logger.warning(f"文件{path}分割后没有有效文本内容，跳过")
                    continue

                # 批量插入优化：每批最多插入50个chunk
                batch_size = 50
                for i in range(0, len(split_document), batch_size):
                    batch = split_document[i:i + batch_size]
                    await self.add_documents(batch)
                    logger.debug(
                        f"插入批次 {i // batch_size + 1}/{(len(split_document) + batch_size - 1) // batch_size}")

                # 记录这个已经处理好的文件的md5，避免下次重复加载
                save_md5_hex(md5_hex)

                logger.info(f"文件{path}加载成功，分割为{len(split_document)}个chunk")
            except Exception as e:
                # 记录详细的错误信息
                logger.error(f"文件{path}加载失败", exc_info=True)
                continue

        logger.info("所有文档持久化完成")


if __name__ == '__main__':
    import asyncio
    
    async def main():
        vs = VectorStoreService()

        await vs.load_document()

        retriever = vs.get_retriever()

        res = await asyncio.to_thread(retriever.invoke, "迷路")
        for r in res:
            print(r.page_content)
            print("-" * 20)
    
    asyncio.run(main())