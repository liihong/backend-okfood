from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeeklyMenuSlot(Base):
    """每周槽位：week_start（周一）+ slot（1–7）对应具体供餐日；本周/下周仅 week_start 不同。"""

    __tablename__ = "weekly_menu_slot"
    __table_args__ = (UniqueConstraint("week_start", "slot", name="uk_weekly_slot_week_day"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    dish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("menu_dish.id", onupdate="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
