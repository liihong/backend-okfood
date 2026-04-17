from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    wechat_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    wx_mini_openid: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    remarks: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    # 每配送日份数：确认送达一次按该倍数扣 balance（默认 1）
    daily_meal_units: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # 周卡/月卡累计「总次数」分母；入账时与 balance 同步按卡型 +6 / +24（剩余/总 展示）
    meal_quota_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 与 MySQL ENUM 取值一致，业务校验在 Pydantic / Service
    plan_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_leaved_tomorrow: Mapped[bool] = mapped_column(Boolean, default=False)
    leave_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    leave_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_low_balance_notify_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
