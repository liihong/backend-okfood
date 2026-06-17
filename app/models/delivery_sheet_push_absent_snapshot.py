"""当日首次配送大表顺丰推单时，记录业务日请假会员 id（推单后禁止因取消请假并入大表）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class DeliverySheetPushAbsentSnapshot(Base):
    __tablename__ = "delivery_sheet_push_absent_snapshots"

    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), primary_key=True
    )
    delivery_date: Mapped[date] = mapped_column(Date, primary_key=True)
    meal_period: Mapped[str] = mapped_column(String(16), primary_key=True, default="lunch")
    absent_member_ids: Mapped[list[Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="首次推单时刻业务日请假会员 members.id 列表",
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=beijing_now_naive,
    )
