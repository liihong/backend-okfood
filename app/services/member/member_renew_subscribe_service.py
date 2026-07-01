"""续费提醒订阅消息：完善资料页授权额度 + 扣次后低余额触达。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.timeutil import today_shanghai
from app.integrations.wechat_mini import try_notify_member_renew_remind

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.member import Member

logger = logging.getLogger(__name__)


def _try_consume_quota_and_send(db: Session, member: Member) -> bool:
    """余额已 <= 阈值、有额度、有 openid 时尝试下发；成功则额度 -1。"""
    threshold = int(settings.LOW_BALANCE_THRESHOLD)
    balance = int(member.balance)
    if balance > threshold:
        return False
    if int(member.wx_renew_remind_quota or 0) <= 0:
        return False
    oid = (member.wx_mini_openid or "").strip()
    if not oid:
        return False

    sent = try_notify_member_renew_remind(
        oid,
        balance=balance,
        db=db,
        tenant_id=int(member.tenant_id),
    )
    if not sent:
        return False

    member.wx_renew_remind_quota = max(0, int(member.wx_renew_remind_quota or 0) - 1)
    member.last_low_balance_notify_date = today_shanghai()
    logger.info(
        "续费提醒已下发 member_id=%s balance=%s quota_left=%s",
        member.id,
        balance,
        member.wx_renew_remind_quota,
    )
    return True


def grant_renew_remind_quota(db: Session, member: Member) -> int:
    """用户在完善资料页同意订阅授权后 +1 额度；若当前已低余额则尝试立即下发。"""
    member.wx_renew_remind_quota = int(member.wx_renew_remind_quota or 0) + 1
    _try_consume_quota_and_send(db, member)
    return int(member.wx_renew_remind_quota)


def try_send_renew_remind_after_balance_change(
    db: Session,
    member: Member,
    *,
    balance_before: int,
    meal_period: str = "lunch",
) -> bool:
    """扣次后余额刚进入低余额区间（>阈值 → <=阈值）且仍有额度时下发续费提醒。"""
    from app.models.enums import MealPeriod

    threshold = int(settings.LOW_BALANCE_THRESHOLD)
    period = (meal_period or MealPeriod.LUNCH.value).strip().lower()
    before = int(balance_before)
    if period == MealPeriod.DINNER.value:
        from app.models.member_meal_period_state import MemberMealPeriodState
        from app.services.meal_period.balance import dinner_balance_and_quota

        row = db.get(
            MemberMealPeriodState,
            {"member_id": int(member.id), "meal_period": MealPeriod.DINNER.value},
        )
        after, _ = dinner_balance_and_quota(row)
    else:
        after = int(member.balance)
    if before <= threshold or after > threshold:
        return False
    return _try_consume_quota_and_send(db, member)


def reset_renew_remind_on_recharge(member: Member, *, balance_before: int, balance_after: int) -> None:
    """续卡入账后余额回到阈值以上，清低余额提醒日以便下一周期再次触达。"""
    threshold = int(settings.LOW_BALANCE_THRESHOLD)
    if int(balance_before) <= threshold < int(balance_after):
        member.last_low_balance_notify_date = None
