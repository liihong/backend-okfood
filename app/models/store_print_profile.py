"""门店打印机配置（本地 Lodop / 云标签机）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class StorePrintProfile(Base):
    __tablename__ = "store_print_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    brand: Mapped[str] = mapped_column(String(32), nullable=False)
    cloud_sn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cloud_device_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    paper_preset: Mapped[str] = mapped_column(String(32), default="custom", nullable=False)
    paper_width_mm: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    paper_height_mm: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    local_printer_name_hint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    margin_top_mm: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    margin_left_mm: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
