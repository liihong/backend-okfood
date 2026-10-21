"""晚餐单独暂停与指定配送日。

只给晚餐应配、晚餐日程、开卡赠送和后台档案使用。
禁止写入 members.delivery_deferred，午餐大表、午餐扣次、午餐请假不得调用本模块。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.meal_period.balance import ensure_dinner_period_state


def dinner_schedule_allows_delivery(
    *,
    entitled: bool,
    dinner_delivery_paused: bool,
    dinner_deliver_on: date | None,
    delivery_date: date,
) -> bool:
    """这一天是否进入晚餐配送名单。

    指定配送日等于履约日：进这一天。赠送晚餐没有晚餐资格，靠这一条进单。
    其他日子：必须已有晚餐资格，且没有勾选暂停晚餐。
    未暂停的正式晚餐/全餐仍按原规则每天进单，指定日期不会把他们收成只送一天。
    """
    if dinner_deliver_on is not None and dinner_deliver_on == delivery_date:
        return True
    if not entitled:
        return False
    if dinner_delivery_paused:
        return False
    return True


def dinner_pause_value_for_card_credit(*, paid_dinner: bool, gift_dinner: int) -> bool | None:
    """开卡后晚餐暂停应写成什么。

    正式晚餐或全餐（本张卡餐段含晚餐）返回 False：不强制暂停，并清掉以前赠送留下的暂停。
    只有赠送晚餐、卡本身不含晚餐时返回 True：默认暂停，等客服指定配送日。
    都没有返回 None：不改会员当前的暂停标记。
    """
    if paid_dinner:
        return False
    if int(gift_dinner or 0) > 0:
        return True
    return None


def apply_dinner_pause_after_card_credit(
    db: Session,
    member: Member,
    *,
    paid_dinner: bool,
    gift_dinner: int,
) -> None:
    """按开卡种类写晚餐暂停。不改午餐暂停，不改工单餐段快照。"""
    paused = dinner_pause_value_for_card_credit(paid_dinner=paid_dinner, gift_dinner=gift_dinner)
    if paused is None:
        return
    row = ensure_dinner_period_state(db, int(member.id))
    row.dinner_delivery_paused = paused
    # 开卡当时不指定配送日。客服稍后在档案里选某一天，选日期本身不会把暂停打开。
    row.dinner_deliver_on = None
    db.add(row)


def apply_admin_dinner_schedule_update(
    db: Session,
    member: Member,
    *,
    set_paused: bool,
    paused: bool | None,
    set_deliver_on: bool,
    deliver_on: date | None,
) -> str | None:
    """后台改晚餐暂停或指定配送日。只提交的字段才改，指定日期不会连带改暂停。

    返回操作摘要；没有变化时返回 None。没有晚餐行且本次是「不暂停、清空日期」时不新建行。
    """
    if not set_paused and not set_deliver_on:
        return None
    from app.models.enums import MealPeriod

    row = db.get(
        MemberMealPeriodState,
        {"member_id": int(member.id), "meal_period": MealPeriod.DINNER.value},
    )
    if row is None and not (set_paused and paused) and not (set_deliver_on and deliver_on is not None):
        return None
    if row is None:
        row = ensure_dinner_period_state(db, int(member.id))
    bits: list[str] = []
    if set_paused and paused is not None and bool(row.dinner_delivery_paused) != bool(paused):
        row.dinner_delivery_paused = bool(paused)
        bits.append("暂停晚餐" if paused else "取消暂停晚餐")
    if set_deliver_on and row.dinner_deliver_on != deliver_on:
        row.dinner_deliver_on = deliver_on
        bits.append(
            f"晚餐指定配送日 {deliver_on.isoformat()}" if deliver_on is not None else "清空晚餐指定配送日"
        )
    if not bits:
        return None
    db.add(row)
    return "；".join(bits)
