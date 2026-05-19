"""门店：会员与菜单以门店为边界；门店配置从原 app_settings 能力迁移至此表（每门店一行）。"""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", onupdate="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    store_logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    store_lng: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    store_lat: Mapped[float | None] = mapped_column(Numeric(11, 8), nullable=True)
    leave_deadline_time: Mapped[time] = mapped_column(Time, nullable=False)
    courier_delivery_base_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("4.00"))
    courier_delivery_extra_per_unit_yuan: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("1.00")
    )
    member_card_week_price_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("168.00"))
    member_card_month_price_yuan: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("669.00"))
    # 可选划线价：大于对应「微信支付标价」时小程序会员卡区启用「活动价」样式
    member_card_week_list_price_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    member_card_month_list_price_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 每日 22:00（上海）自动向顺丰推送「次日」配送业务日订单；关闭时仍走管理端手动推单
    sf_nightly_auto_push_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 订单管理「推顺丰」(单次点餐)：createorder 使用此处 shop_id，与租户对接中的顺丰店铺（大表夜间/手动推单）可不同
    sf_retail_push_shop_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sf_retail_push_shop_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # UU 跑腿开放平台参数（预留，尚未对接发单接口）
    uu_open_app_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uu_open_app_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    wechat_pay_ssl_cert_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    wechat_pay_ssl_key_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
