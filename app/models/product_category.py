from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class ProductCategory(Base):
    """商品分类（如：每周餐品），每门店独立一套。"""

    __tablename__ = "product_category"
    __table_args__ = (UniqueConstraint("store_id", "code", name="uk_product_category_store_code"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("product_category.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
