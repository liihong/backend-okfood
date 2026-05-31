from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class SingleMealOrder(Base):
    """会员单次点餐：支付与履约状态独立；片区派单字段见 routing_area / courier_id。

    ``created_at`` / ``updated_at`` 存 **北京时间**（无时区列，与 Asia/Shanghai 墙钟一致）。
    """

    __tablename__ = "single_meal_orders"
    __table_args__ = (UniqueConstraint("store_id", "out_trade_no", name="uk_smo_store_out_trade_no"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", onupdate="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    out_trade_no: Mapped[str] = mapped_column(String(32), index=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("members.id", onupdate="CASCADE"), index=True)
    dish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("menu_dish.id", onupdate="CASCADE"), index=True)
    member_address_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("member_addresses.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    store_pickup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, index=True)
    routing_area: Mapped[str] = mapped_column(String(64))
    amount_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    original_amount_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    coupon_discount_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    member_coupon_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("member_coupons.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    pay_status: Mapped[str] = mapped_column(String(10), default="未支付")
    pay_channel: Mapped[str | None] = mapped_column(String(16), nullable=True)
    wx_transaction_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fulfillment_status: Mapped[str] = mapped_column(String(20), default="pending")
    courier_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("couriers.courier_id", onupdate="CASCADE"), nullable=True, index=True
    )
    sf_same_city_push_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("sf_same_city_pushes.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    sf_order_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
