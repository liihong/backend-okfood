from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DeliveryStatus


class DeliveryLog(Base):
    __tablename__ = "delivery_logs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("members.id", onupdate="CASCADE"),
        index=True,
    )
    delivery_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=DeliveryStatus.PENDING.value)
    courier_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("couriers.courier_id", onupdate="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
