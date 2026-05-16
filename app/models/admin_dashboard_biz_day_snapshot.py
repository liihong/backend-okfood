"""营业概览按业务锚日归档：与智能配送大表同一口径，便于历史查询、避免事后改档导致数字漂移。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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
    today_leave_members: Mapped[int] = mapped_column(Integer, nullable=False)
    today_meals_to_prepare: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="与当日配送大表各分组 meal_total 之和一致（到家+自提，含已送后扣次剔除仍并入大表者）",
    )
    tomorrow_leave_members: Mapped[int] = mapped_column(Integer, nullable=False)
    tomorrow_meals_to_prepare: Mapped[int] = mapped_column(Integer, nullable=False)
    today_expire_one_unit_members: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="锚定日应履约且 balance 恰等于每配送日份数（仅剩 1 次）的会员数",
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="首次写入或 force_recompute 覆盖时间",
    )
