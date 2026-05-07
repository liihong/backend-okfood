"""营业概览按业务锚日归档：与智能配送大表同一口径，便于历史查询、避免事后改档导致数字漂移。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminDashboardBizDaySnapshot(Base):
    __tablename__ = "admin_dashboard_biz_day_snapshots"

    business_anchor_date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,
        comment="统计锚定业务日(上海)：「今日」指标对应该日；「明日」为日历次日",
    )
    today_leave_members: Mapped[int] = mapped_column(Integer, nullable=False)
    today_meals_to_prepare: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="与当日配送大表各分组 meal_total 之和一致（到家+自提，含已送后扣次剔除仍并入大表者）",
    )
    tomorrow_leave_members: Mapped[int] = mapped_column(Integer, nullable=False)
    tomorrow_meals_to_prepare: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="首次写入或 force_recompute 覆盖时间",
    )
