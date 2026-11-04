"""每份标配：筷子、小勺这类每餐都有、且不随菜品变化的耗材。打包袋不放这里。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class PackagingStandardLine(Base):
    """门店级每份数量。午餐和晚餐各乘各的出餐份数。"""

    __tablename__ = "packaging_standard_line"
    __table_args__ = (UniqueConstraint("store_id", "sku_id", name="uk_packaging_standard_store_sku"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("packaging_sku.id", onupdate="CASCADE"), nullable=False
    )
    qty_per_portion: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
