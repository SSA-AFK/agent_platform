from fastapi import APIRouter

from test.rag.rag_service import logger
from backed.schema.rag import RagRequest
from backed.utils.response import success_response
from test.test_04_rag.rag import rag_service

rag_router = APIRouter(prefix="/rag", tags=["rag"])

@rag_router.post("/chat")
async def chat(query: RagRequest):
    """
     rag 聊天
    """
    logger.info(f"query: {query.query}")
    answer = rag_service.chat(query.query)
    return success_response(data={"answer": "hello world"})