from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MemberCardOrder(Base):
    """后台开卡工单：缴费渠道、状态及是否已同步会员次数。"""

    __tablename__ = "member_card_orders"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("members.id", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )
    card_kind: Mapped[str] = mapped_column(String(10))
    pay_channel: Mapped[str] = mapped_column(String(10))
    pay_status: Mapped[str] = mapped_column(String(10), default="未缴")
    amount_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    applied_to_member: Mapped[bool] = mapped_column(Boolean, default=False)
    out_trade_no: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    wx_transaction_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
