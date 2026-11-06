"""包装耗材流水。结存不能脱离流水单独修改。"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class PackagingStockTxn(Base):
    """期初、入库、自动领用、盘点。有任意一条流水才算已期初，晚上才会扣这个品。"""

    __tablename__ = "packaging_stock_txn"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("packaging_sku.id", onupdate="CASCADE"), nullable=False, index=True
    )
    txn_type: Mapped[str] = mapped_column(String(32), nullable=False)
    qty_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_after: Mapped[int] = mapped_column(Integer, nullable=False)
    biz_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    meal_period: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="自动领用才填 lunch/dinner")
    operator: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
