"""微信支付结果通知：按商户单号分发至单笔点餐或会员开卡工单。"""

import logging

from sqlalchemy.orm import Session

from app.integrations.wechat_pay_v2 import parse_wechat_pay_notify
from app.services.member_card_pay_service import finalize_member_card_order_wechat_pay
from app.services.single_meal_order_service import finalize_single_meal_order_wechat_pay

logger = logging.getLogger(__name__)


def apply_wechat_pay_notify(db: Session, data: dict[str, str]) -> tuple[bool, str]:
    """验签后依次尝试单笔点餐、开卡工单；返回 (是否 SUCCESS, 原因)。"""
    ok, reason, parsed = parse_wechat_pay_notify(data)
    if not ok or parsed is None:
        return False, reason

    sm_ok, sm_reason = finalize_single_meal_order_wechat_pay(db, parsed)
    if sm_ok:
        return True, sm_reason
    if sm_reason != "order_not_found":
        return False, sm_reason

    card_ok, card_reason = finalize_member_card_order_wechat_pay(db, parsed)
    if card_ok:
        return True, card_reason
    if card_reason != "order_not_found":
        return False, card_reason

    logger.warning("微信回调商户单号无匹配订单: %s", parsed.out_trade_no)
    return False, "order_not_found"
