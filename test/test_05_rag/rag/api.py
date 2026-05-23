from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from rag_service import VectorMemoryRag
from langchain_core.messages import HumanMessage, AIMessage
import uvicorn

app = FastAPI(title="RAG Memory API", description="带有记忆功能的 RAG 服务 API")

# 初始化带记忆功能的 RAG 服务
memory_rag = VectorMemoryRag()

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    answer: str
    session_id: str

class SessionHistoryItem(BaseModel):
    type: str
    content: str

class SessionHistoryResponse(BaseModel):
    session_id: str
    history: List[SessionHistoryItem]

class SessionSummaryResponse(BaseModel):
    session_id: str
    summary: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """聊天接口，支持多会话记忆"""
    try:
        answer = await memory_rag.chat(request.query, request.session_id)
        return ChatResponse(answer=answer, session_id=request.session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")

@app.get("/session/history", response_model=SessionHistoryResponse)
async def get_session_history(
    session_id: str = Query(default="default", description="会话ID"),
    limit: int = Query(default=10, ge=1, le=100, description="历史记录条数限制")
):
    """获取会话历史记录"""
    try:
        history = await memory_rag.get_session_history(session_id, limit=limit)
        # 转换为可序列化的格式
        history_items = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                history_items.append(SessionHistoryItem(type="human", content=msg.content))
            elif isinstance(msg, AIMessage):
                history_items.append(SessionHistoryItem(type="ai", content=msg.content))
        return SessionHistoryResponse(session_id=session_id, history=history_items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话历史时出错: {str(e)}")

@app.get("/session/summary", response_model=SessionSummaryResponse)
async def get_session_summary(
    session_id: str = Query(default="default", description="会话ID")
):
    """获取会话摘要"""
    try:
        summary = await memory_rag.get_session_summary(session_id)
        return SessionSummaryResponse(session_id=session_id, summary=summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话摘要时出错: {str(e)}")

@app.delete("/session/clear")
async def clear_session(
    session_id: str = Query(default="default", description="会话ID")
):
    """清理会话"""
    try:
        await memory_rag.clear_session(session_id)
        return {"message": f"会话 {session_id} 已清理"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理会话时出错: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
