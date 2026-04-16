from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DeliveryRegion(Base):
    __tablename__ = "delivery_regions"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    polygon_json: Mapped[dict | list] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    courier_links: Mapped[list["DeliveryRegionCourier"]] = relationship(
        "DeliveryRegionCourier",
        back_populates="region",
        cascade="all, delete-orphan",
        order_by="DeliveryRegionCourier.sort_order",
    )


class DeliveryRegionCourier(Base):
    __tablename__ = "delivery_region_couriers"
    __table_args__ = (UniqueConstraint("region_id", "courier_id", name="uk_region_courier"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("delivery_regions.id", ondelete="CASCADE"), index=True)
    courier_id: Mapped[str] = mapped_column(String(50), ForeignKey("couriers.courier_id", ondelete="CASCADE"), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    region: Mapped["DeliveryRegion"] = relationship("DeliveryRegion", back_populates="courier_links")
    courier: Mapped["Courier"] = relationship("Courier", lazy="selectin")
