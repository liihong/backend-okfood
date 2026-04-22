"""骑手配送费计价：同一地址一单，首份基础价，每多一份加价（与确认送达时的扣次份数一致）。"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.store_config_service import get_courier_delivery_fee_config


def courier_delivery_fee_yuan_for_meal_units(db: Session, meal_units: int) -> Decimal:
    """
    计算一单（同一会员、同一默认地址的一次确认送达）应付骑手配送费。

    - meal_units：当日扣次份数，与 Member.daily_meal_units 封顶规则一致，调用方已规范化时传入即可。
    - 单价来自 `app_settings`（后台门店配置），无记录时回退 .env 默认。
    """
    try:
        u = int(meal_units)
    except (TypeError, ValueError):
        u = 1
    u = max(1, u)
    base, extra = get_courier_delivery_fee_config(db)
    return base + extra * Decimal(u - 1)
