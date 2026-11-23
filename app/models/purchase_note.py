"""采购资料。

只给客服留一份「去哪里买」的备忘：链接、微信、手机号或其他联系方式。
不挂菜品、耗材档案、库存结存或供应商主数据，删改不会动库存。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class PurchaseNote(Base):
    """门店采购备忘。同一名称可以有多条，方便记下不同渠道。"""

    __tablename__ = "purchase_note"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    # ingredient=食材类，consumable=耗材类。只用于列表筛选，不指向别的表。
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # link / wechat / phone / other
    record_method: Mapped[str] = mapped_column(String(16), nullable=False)
    contact_value: Mapped[str] = mapped_column(String(500), nullable=False, comment="链接、微信号、手机号或其他查找内容")
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="如淘宝、拼多多、微信")
    supplier_label: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="简称或供应方，便于认人")
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
