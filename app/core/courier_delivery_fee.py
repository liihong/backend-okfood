"""骑手配送费计价：同一地址一单，首份基础价，每多一份加价（与确认送达时的扣次份数一致）。"""

from decimal import Decimal

from app.core.config import get_settings


def courier_delivery_fee_yuan_for_meal_units(meal_units: int) -> Decimal:
    """
    计算一单（同一会员、同一默认地址的一次确认送达）应付骑手配送费。

    - meal_units：当日扣次份数，与 Member.daily_meal_units 封顶规则一致，调用方已规范化时传入即可。
    """
    try:
        u = int(meal_units)
    except (TypeError, ValueError):
        u = 1
    u = max(1, u)
    s = get_settings()
    base = s.COURIER_DELIVERY_BASE_YUAN
    extra = s.COURIER_DELIVERY_EXTRA_PER_UNIT_YUAN
    return base + extra * Decimal(u - 1)
