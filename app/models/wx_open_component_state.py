"""微信开放平台 component 全局状态（verify_ticket）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class WxOpenComponentState(Base):
    __tablename__ = "wx_open_component_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    verify_ticket: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ticket_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
