"""礼品券活动：圈人规则与厨房标签文案。与营销代金券、会员备注无关。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class GiftCouponCampaign(Base):
    """一次跟餐赠品活动（如「8月开卡礼品券」）。"""

    __tablename__ = "gift_coupon_campaigns"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", onupdate="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    #: 打印标签上给后厨看的礼品名，不写入 members.remarks
    sheet_label: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False, index=True)
    #: ["month"] / ["quarter"]；判定看开卡工单模版种类，禁止用 members.plan_type
    plan_kinds: Mapped[list] = mapped_column(JSON, nullable=False)
    credited_from: Mapped[date] = mapped_column(Date, nullable=False)
    credited_to: Mapped[date] = mapped_column(Date, nullable=False)
    exclude_membership_refunded: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    match_mode: Mapped[str] = mapped_column(String(32), default="any_in_range", nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=beijing_now_naive, onupdate=beijing_now_naive
    )
