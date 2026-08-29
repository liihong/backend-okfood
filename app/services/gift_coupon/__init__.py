"""礼品券模块对外入口。"""

from app.services.gift_coupon.hooks import try_auto_grant_after_card_credit

__all__ = ["try_auto_grant_after_card_credit"]
