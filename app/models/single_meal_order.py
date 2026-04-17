from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SingleMealOrder(Base):
    """会员单次点餐：支付与履约状态独立；片区派单字段见 routing_area / courier_id。"""

    __tablename__ = "single_meal_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    out_trade_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("members.id", onupdate="CASCADE"), index=True)
    dish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("menu_dish.id", onupdate="CASCADE"), index=True)
    member_address_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("member_addresses.id", onupdate="CASCADE"), index=True
    )
    delivery_date: Mapped[date] = mapped_column(Date, index=True)
    routing_area: Mapped[str] = mapped_column(String(64))
    amount_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    pay_status: Mapped[str] = mapped_column(String(10), default="未支付")
    pay_channel: Mapped[str | None] = mapped_column(String(16), nullable=True)
    wx_transaction_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fulfillment_status: Mapped[str] = mapped_column(String(20), default="pending")
    courier_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("couriers.courier_id", onupdate="CASCADE"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
