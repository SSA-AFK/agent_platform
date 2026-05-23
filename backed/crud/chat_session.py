import uuid
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backed.models.chat_session import ChatSession


async def create_chat_session(db: AsyncSession, user_id: int, title: str = "新对话") -> ChatSession:
    """创建一个新的聊天会话"""
    session_id = str(uuid.uuid4())
    new_session = ChatSession(
        user_id=user_id,
        session_id=session_id,
        title=title
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session

async def get_user_sessions(db: AsyncSession, user_id: int) -> Sequence[ChatSession]:
    """获取用户的所有聊天会话，按更新时间倒序排列"""
    query = select(ChatSession).where(ChatSession.user_id == user_id).order_by(desc(ChatSession.updated_at))
    result = await db.execute(query)
    return result.scalars().all()

async def get_session_by_id(db: AsyncSession, session_id: str, user_id: int) -> ChatSession:
    """根据 session_id 获取会话，确保是当前用户的"""
    query = select(ChatSession).where(ChatSession.session_id == session_id, ChatSession.user_id == user_id)
    result = await db.execute(query)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session

async def update_session_title(db: AsyncSession, session_id: str, user_id: int, title: str) -> ChatSession:
    """更新会话标题"""
    session = await get_session_by_id(db, session_id, user_id)
    session.title = title
    await db.commit()
    await db.refresh(session)
    return session

async def delete_chat_session(db: AsyncSession, session_id: str, user_id: int):
    """删除会话"""
    session = await get_session_by_id(db, session_id, user_id)
    await db.delete(session)
    await db.commit()
    return True