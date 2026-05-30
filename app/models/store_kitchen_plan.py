"""门店后厨计划出单：按业务日手动设定，供营业概览顶卡联动展示。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class StoreKitchenPlan(Base):
    __tablename__ = "store_kitchen_plans"

    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), primary_key=True
    )
    business_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="上海业务日")
    planned_total: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="后厨计划出单总数（份/单）"
    )
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=beijing_now_naive
    )
