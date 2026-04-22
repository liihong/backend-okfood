from datetime import datetime, time

from sqlalchemy import DateTime, Integer, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    leave_deadline_time: Mapped[time] = mapped_column(Time)
    store_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    store_logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    store_lng: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    store_lat: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
