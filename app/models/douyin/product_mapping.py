"""抖音团购：商品与本地权益映射。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class DouyinProductMapping(Base):
    __tablename__ = "douyin_product_mappings"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", onupdate="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    douyin_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    douyin_sku_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    douyin_product_out_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    grant_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
