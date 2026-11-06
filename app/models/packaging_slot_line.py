"""本周某一餐的用盒。晚上只读这张表，避免事后改菜品默认时回写已经扣过的餐。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class PackagingSlotLine(Base):
    """挂在 weekly_menu_slot 上。清空槽位时随槽位级联删除，不挡住原有换菜。"""

    __tablename__ = "packaging_slot_line"
    __table_args__ = (UniqueConstraint("slot_id", "sku_id", name="uk_packaging_slot_line"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    slot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("weekly_menu_slot.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("packaging_sku.id", onupdate="CASCADE"), nullable=False
    )
    qty_per_portion: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
