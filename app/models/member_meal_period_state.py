"""分餐段运营态（份数/请假）：资格仍由开卡工单 meal_periods_snapshot 决定，本表仅存晚餐侧配置。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class MemberMealPeriodState(Base):
    __tablename__ = "member_meal_period_state"

    member_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("members.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    meal_period: Mapped[str] = mapped_column(String(16), primary_key=True)
    daily_meal_units: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    daily_meal_units_pending: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_leaved_tomorrow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tomorrow_leave_target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    leave_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    leave_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=beijing_now_naive, onupdate=beijing_now_naive
    )
