"""当日首次配送大表顺丰推单时，记录各会员每配送日份数（推单后大表统计读快照，防当日改份数漂移）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class DeliverySheetPushUnitsSnapshot(Base):
    __tablename__ = "delivery_sheet_push_units_snapshots"

    store_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    delivery_date: Mapped[date] = mapped_column(Date, primary_key=True)
    meal_period: Mapped[str] = mapped_column(String(16), primary_key=True, default="lunch")
    member_meal_units: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="首次推单时刻 member_id(字符串)→份数",
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=beijing_now_naive,
    )
