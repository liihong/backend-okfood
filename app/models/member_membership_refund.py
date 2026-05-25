from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class MemberMembershipRefund(Base):
    """会员退卡退款：按剩余次数 × 单次单价退实收，写入财务扣减。"""

    __tablename__ = "member_membership_refunds"

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
    meals_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meals_refunded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meal_quota_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    paid_total_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    consumed_value_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    unit_price_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0, nullable=False)
    refund_amount_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    operator: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, index=True)
