from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from models.users import User

class Base(DeclarativeBase):
    pass

class Itinerary(Base):
    """
    我的行程表 ORM模型
    """
    __tablename__ = 'itinerary'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="行程ID")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id), nullable=False, comment="用户ID")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="行程标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="行程详细内容(Markdown/Text)")
    route_data: Mapped[Optional[dict]] = mapped_column(JSON, comment="高德地图坐标/路线结构化数据")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<Itinerary(id={self.id}, title='{self.title}', user_id={self.user_id})>"
