from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backed.models.users import User


class Base(DeclarativeBase):
    pass

class ChatSession(Base):
    """
    聊天会话表 ORM模型
    """
    __tablename__ = 'chat_session'

    # 创建索引：通过 user_id 快速查询会话列表
    __table_args__ = (
        Index('fk_chat_session_user_idx', 'user_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="自增主键ID")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id), nullable=False, comment="归属用户ID")
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="会话的 UUID (对应 LangGraph 的 thread_id)")
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="新对话", comment="会话标题")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, session_id='{self.session_id}', title='{self.title}')>"
