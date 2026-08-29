"""礼品券资格账本：一人一活动一张。未上当日大表不得改状态。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class GiftCouponEntitlement(Base):
    """会员持有的一张礼品券资格。"""

    __tablename__ = "gift_coupon_entitlements"
    __table_args__ = (
        UniqueConstraint("campaign_id", "member_id", name="uk_gce_campaign_member"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    campaign_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("gift_coupon_campaigns.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("members.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", onupdate="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="granted", nullable=False, index=True)
    grant_source: Mapped[str] = mapped_column(String(16), default="rule", nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, nullable=False)
    granted_by: Mapped[str] = mapped_column(String(64), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    redeemed_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    redeemed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    redeemed_sheet_view: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
