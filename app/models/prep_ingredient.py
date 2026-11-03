"""开菜单食材：出成率按门店维护，不改菜品库。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class PrepIngredient(Base):
    """门店食材。克重食材用出成率把毛菜折成净菜；按个计的出成率固定为 1。"""

    __tablename__ = "prep_ingredient"
    __table_args__ = (
        UniqueConstraint("store_id", "name", name="uk_prep_ingredient_store_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, comment="g=克；piece=个")
    yield_rate: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("1"), comment="净菜/毛菜，大于 0 且不超过 1"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
