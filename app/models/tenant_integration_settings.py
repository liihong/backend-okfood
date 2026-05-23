"""租户级对接配置：小程序与微信支付、顺丰等同城参数；未填字段回退全局环境变量。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class TenantIntegrationSettings(Base):
    __tablename__ = "tenant_integration_settings"

    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", onupdate="CASCADE", ondelete="CASCADE"), primary_key=True
    )
    wx_mini_appid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wx_mini_secret: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wechat_pay_mch_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    wechat_pay_api_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wechat_pay_notify_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    wechat_pay_ssl_cert_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    wechat_pay_ssl_key_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    wx_subscribe_delivery_tmpl_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wx_subscribe_renew_tmpl_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    sf_open_dev_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sf_open_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sf_open_shop_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sf_open_shop_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sf_pickup_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sf_pickup_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sf_city_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
