"""商城零售订单明细行（一单多 SKU）。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class StoreRetailOrderItem(Base):
    __tablename__ = "store_retail_order_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("store_retail_orders.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    retail_product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("store_retail_products.id", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    spu_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    product_title: Mapped[str] = mapped_column(String(256), nullable=False)
    spu_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    spec_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit_price_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    line_amount_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
