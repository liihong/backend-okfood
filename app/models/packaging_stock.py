"""包装耗材结存。一个品一行，数量只随流水变动。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class PackagingStock(Base):
    """当前结存。允许为负，用来表示已经欠货。"""

    __tablename__ = "packaging_stock"

    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("packaging_sku.id", onupdate="CASCADE", ondelete="CASCADE"), primary_key=True
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
