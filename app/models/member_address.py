from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MemberAddress(Base):
    __tablename__ = "member_addresses"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("members.id", ondelete="CASCADE", onupdate="CASCADE"),
        index=True,
    )
    contact_name: Mapped[str] = mapped_column(String(100))
    contact_phone: Mapped[str] = mapped_column(String(20))
    delivery_region_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("delivery_regions.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    detail_address: Mapped[str] = mapped_column(String(500))
    map_location_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    door_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lng: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    lat: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
