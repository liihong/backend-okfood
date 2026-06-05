"""抖音团购：验券兑换流水。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class DouyinCertificateRedemption(Base):
    __tablename__ = "douyin_certificate_redemptions"

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
        nullable=False,
        index=True,
    )
    code_masked: Mapped[str | None] = mapped_column(String(32), nullable=True)
    douyin_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    certificate_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    douyin_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    douyin_sku_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    douyin_product_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mapping_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), nullable=True
    )
    grant_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grant_target_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), nullable=True
    )
    grant_result_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grant_result_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    error_msg: Mapped[str | None] = mapped_column(String(512), nullable=True)
    verify_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    douyin_verify_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    amount_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, index=True)
