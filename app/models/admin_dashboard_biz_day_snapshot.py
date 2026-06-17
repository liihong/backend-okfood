"""营业概览按业务锚日归档：与智能配送大表同一口径，便于历史查询、避免事后改档导致数字漂移。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class AdminDashboardBizDaySnapshot(Base):
    __tablename__ = "admin_dashboard_biz_day_snapshots"

    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), primary_key=True
    )
    business_anchor_date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,
        comment="统计锚定业务日(上海)：「今日」指标对应该日；「明日」为日历次日",
    )
    meal_period: Mapped[str] = mapped_column(
        String(16),
        primary_key=True,
        default="lunch",
        comment="lunch/dinner；午晚分轨归档",
    )
    today_leave_members: Mapped[int] = mapped_column(Integer, nullable=False)
    today_meals_to_prepare: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="与当日配送大表各分组 meal_total 之和一致（到家+自提，含已送后扣次剔除仍并入大表者）",
    )
    kitchen_output_total: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="锚定日后厨出餐份数归档",
    )
    tomorrow_leave_members: Mapped[int] = mapped_column(Integer, nullable=False)
    tomorrow_meals_to_prepare: Mapped[int] = mapped_column(Integer, nullable=False)
    today_expire_one_unit_members: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="锚定日已消费殆尽的末次出餐份数（份数非人数），口径同 count_expire_one_unit_members_for_business_day",
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=beijing_now_naive,
        comment="首次写入或 force_recompute 覆盖时间",
    )
