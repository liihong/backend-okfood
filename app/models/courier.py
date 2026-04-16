from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Courier(Base):
    __tablename__ = "couriers"

    courier_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fee_pending: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    fee_settled: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    pin_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
