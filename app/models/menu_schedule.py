from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MenuSchedule(Base):
    """某日供餐排期，指向菜品库中的一条。"""

    __tablename__ = "menu_schedule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    menu_date: Mapped[date] = mapped_column(Date, unique=True)
    dish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("menu_dish.id", onupdate="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
