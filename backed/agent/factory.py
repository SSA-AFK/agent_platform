import os
from abc import ABC, abstractmethod
from typing import Optional, List
import requests
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseLanguageModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

class BaseFactory(ABC):
    @abstractmethod
    def generator(self)-> Optional[Embeddings | BaseLanguageModel]:
        pass

class ChatModelFactory(BaseFactory):
    def generator(self)-> Optional[BaseLanguageModel]:
        base_url = os.getenv("BASE_URL")
        api_key = os.getenv("OPENAI_API_KEY")
        chat_model =os.getenv("CHAT_MODEL")

        return ChatOpenAI(
            model = chat_model,
            api_key = api_key,
            base_url = base_url
        )


class QwenEmbeddings(Embeddings):
    """自定义Qwen Embeddings类，正确处理输入格式"""

    def __init__(self, model: str, base_url: str, api_key: str):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入文档列表（批量处理）"""
        # 确保texts是字符串列表
        texts = [str(text) for text in texts]

        batch_size = 10  # 每批不超过10条记录
        all_embeddings = []

        # 分批处理
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            print(
                f"🔄 处理批次 {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size} (共 {len(batch_texts)} 条)")

            response = requests.post(
                f"{self.base_url}/embeddings",
                headers=self.headers,
                json={
                    "model": self.model,
                    "input": batch_texts
                }
            )

            if response.status_code != 200:
                raise Exception(f"Embedding API error: {response.text}")

            data = response.json()
            batch_embeddings = [item["embedding"] for item in data["data"]]
            all_embeddings.extend(batch_embeddings)

        print(f"✅ 完成所有嵌入，共 {len(all_embeddings)} 条")
        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        return self.embed_documents([str(text)])[0]

class EmbeddingFactory(BaseFactory):
    def generator(self)-> Optional[Embeddings]:
        api_key = os.getenv("OPENAI_API_KEY")
        embedding_model = os.getenv("EMBEDDING_MODEL")
        base_url = os.getenv("BASE_URL")
        return QwenEmbeddings(
            model = embedding_model,
            api_key = api_key,
            base_url = base_url
        )

chat_model = ChatModelFactory().generator()
embed_model = EmbeddingFactory().generator()

if __name__ == '__main__':
    print(chat_model.invoke("你好"))