"""菜品配菜行：单份毛菜用量，供开菜单按份数估算。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class DishPrepSopLine(Base):
    """某菜品的一行配菜。数量是单份毛菜（克或个数），净菜由食材出成率折算。"""

    __tablename__ = "dish_prep_sop_line"
    __table_args__ = (
        UniqueConstraint("dish_id", "ingredient_id", name="uk_dish_prep_sop_dish_ingredient"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    dish_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("menu_dish.id", onupdate="CASCADE"), nullable=False, index=True
    )
    ingredient_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("prep_ingredient.id", onupdate="CASCADE"), nullable=False, index=True
    )
    gross_qty_per_portion: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, comment="单份毛菜：克或个数"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
