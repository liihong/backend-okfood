from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MenuSchedule(Base):
    """某日供餐排期，指向菜品库中的一条。"""

    __tablename__ = "menu_schedule"
    __table_args__ = (UniqueConstraint("store_id", "menu_date", name="uk_menu_schedule_store_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    menu_date: Mapped[date] = mapped_column(Date)
    dish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("menu_dish.id", onupdate="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
