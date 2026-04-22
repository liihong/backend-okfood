from datetime import datetime, time
from decimal import Decimal

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
    # 骑手确认送达计费：首份基础价 + 每多一份加价（元）
    courier_delivery_base_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("4.00"))
    courier_delivery_extra_per_unit_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("1.00"))
    # 小程序自助开卡微信支付标价（元）
    member_card_week_price_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("168.00"))
    member_card_month_price_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("669.00"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
