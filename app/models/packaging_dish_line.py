"""菜品默认用盒。换菜时抄到当天槽位，晚上扣库不读这张表。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class PackagingDishLine(Base):
    """某道菜每份要用的盒子。打包袋不能出现在这里。"""

    __tablename__ = "packaging_dish_line"
    __table_args__ = (UniqueConstraint("dish_id", "sku_id", name="uk_packaging_dish_line"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    dish_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("menu_dish.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("packaging_sku.id", onupdate="CASCADE"), nullable=False
    )
    qty_per_portion: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
