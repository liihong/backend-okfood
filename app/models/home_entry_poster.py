"""小程序弹窗海报（按门店 + 场景，每组合一条）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base

# 海报场景：entry=进入小程序，menu=点单菜单页
POSTER_TYPE_ENTRY = "entry"
POSTER_TYPE_MENU = "menu"


class HomeEntryPoster(Base):
    __tablename__ = "home_entry_poster"
    __table_args__ = (
        UniqueConstraint("store_id", "poster_type", name="uk_home_entry_poster_store_type"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False
    )
    poster_type: Mapped[str] = mapped_column(String(32), default=POSTER_TYPE_ENTRY, nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=beijing_now_naive, onupdate=beijing_now_naive
    )
