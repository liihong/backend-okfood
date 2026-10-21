"""会员卡种类模版（后台配置层）：种类手填名称 + 每笔入账餐次；P1 不接支付入账。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class MembershipCardTemplate(Base):
    """单门店多张模版。「种类」为运营自定义文案（周卡、季卡、午晚餐卡等），与「名称」可区分。"""

    __tablename__ = "membership_card_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", onupdate="CASCADE"), index=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    # 仅占位兼容旧数据或后续自动化路由；可为 NULL
    period_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: 覆盖餐段 JSON：["lunch"] / ["dinner"] / ["lunch","dinner"]，默认午餐
    meal_periods: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    #: 午+晚卡是否与午餐一起配送并在午餐履约时连带扣晚餐；默认否（分送）
    deliver_dinner_with_lunch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kind_label: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    meals_grant: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 赠送晚餐次数。0 表示不送。只加晚餐余额，不写入餐段快照，避免和 meals_grant 一样每个餐段各加一次。
    gift_dinner_meals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: 赠送果蔬汁 SKU（store_retail_products.id）。与赠送晚餐互斥。
    gift_retail_product_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    #: 赠送果蔬汁单数。开卡时按这个次数逐笔创建普通商城订单（每笔数量 1），不是一笔数量 N。
    gift_retail_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    list_price_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sale_price_yuan: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    card_style_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intro_short: Mapped[str | None] = mapped_column(String(512), nullable=True)
    purchase_notice: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
