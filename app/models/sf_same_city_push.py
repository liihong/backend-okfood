from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SfSameCityPush(Base):
    """管理端向顺丰同城 createorder 提交后的落库，便于对账与排错。"""

    __tablename__ = "sf_same_city_pushes"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    delivery_date: Mapped[date] = mapped_column(Date, index=True)
    stop_id: Mapped[str] = mapped_column(String(64), index=True)
    shop_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sf_order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sf_bill_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    request_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_callback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_callback_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sf_callback_order_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
