"""日库存损耗/回补流水：剩余不可直接改值，仅通过本表入账。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class DayStockAdjustmentLog(Base):
    __tablename__ = "day_stock_adjustment_logs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    meal_period: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False, comment="负数减可售；正数回补")
    reason_code: Mapped[str] = mapped_column(String(32), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    operator: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=beijing_now_naive)
