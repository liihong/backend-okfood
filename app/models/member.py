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
    remarks: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    # 与 MySQL ENUM 取值一致，业务校验在 Pydantic / Service
    plan_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_leaved_tomorrow: Mapped[bool] = mapped_column(Boolean, default=False)
    leave_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    leave_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_low_balance_notify_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
