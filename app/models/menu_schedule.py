from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class MenuSchedule(Base):
    """某日供餐排期，指向菜品库中的一条。"""

    __tablename__ = "menu_schedule"
    __table_args__ = (
        UniqueConstraint("store_id", "menu_date", "meal_period", name="uk_menu_schedule_store_date_period"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    menu_date: Mapped[date] = mapped_column(Date)
    meal_period: Mapped[str] = mapped_column(String(16), nullable=False, default="lunch")
    dish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("menu_dish.id", onupdate="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
