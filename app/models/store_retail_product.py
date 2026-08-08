"""门店普通商品 SKU（可售最小单元：规格、价格、库存）。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class StoreRetailProduct(Base):
    """SKU 表：历史表名 store_retail_products；对外 retail_product_id 即 SKU id。"""

    __tablename__ = "store_retail_products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    spu_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("store_retail_spus.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sku_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spec_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit_price_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    list_price_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_on_shelf: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # NULL 表示不限库存；非 NULL 时按已占用量（未支付占用 + 已支付）扣减
    stock_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
