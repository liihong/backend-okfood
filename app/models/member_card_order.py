from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class MemberCardOrder(Base):
    """后台开卡工单：缴费渠道、状态及是否已同步会员次数。"""

    __tablename__ = "member_card_orders"
    __table_args__ = (
        UniqueConstraint("store_id", "out_trade_no", name="uk_mco_store_out_trade_no"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", onupdate="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("members.id", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )
    membership_template_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("membership_card_templates.id", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    card_kind: Mapped[str] = mapped_column(String(10))
    pay_channel: Mapped[str] = mapped_column(String(10))
    pay_status: Mapped[str] = mapped_column(String(10), default="未缴")
    amount_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    original_amount_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    coupon_discount_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    member_coupon_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("member_coupons.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    applied_to_member: Mapped[bool] = mapped_column(Boolean, default=False)
    out_trade_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    wx_transaction_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
