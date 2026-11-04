"""包装耗材档案。

只描述门店有哪些盒子、袋子和标配品，不记录结存。
每餐打包袋用 bag_flag=1 标记，全店只能有一行；普通品保持空，避免和「每份一只」重复扣。
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class PackagingSku(Base):
    """门店包装耗材。同一门店名称唯一。"""

    __tablename__ = "packaging_sku"
    __table_args__ = (
        UniqueConstraint("store_id", "name", name="uk_packaging_sku_store_name"),
        # bag_flag 仅打包袋填 1。MySQL 唯一索引允许多个 NULL，所以普通品互不冲突。
        UniqueConstraint("store_id", "bag_flag", name="uk_packaging_sku_store_bag"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    usage_note: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="用途，如沙拉、料汁")
    supplier_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="个")
    safety_stock: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="最低库存；空表示不发采购提醒"
    )
    bag_flag: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="1=每餐固定扣一只的打包袋；普通品为空"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
