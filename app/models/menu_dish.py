from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MenuDish(Base):
    """菜品库：与排期解耦，可单独启用/停用。"""

    __tablename__ = "menu_dish"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("product_category.id", onupdate="CASCADE", ondelete="SET NULL"), nullable=True
    )
    single_order_price_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    spice_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    internal_view_sop: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# 会员端文案（code → 中文）；未设置或 none 时不展示辣度提示
SPICE_LEVEL_MEMBER_LABELS: dict[str, str] = {
    "none": "不辣",
    "mild": "微微辣",
    "medium": "微辣",
    "hot": "较辣",
}
