"""全餐卡「与午餐一起配送」：独立于现网午餐扣次。

午餐履约成功后追加扣晚餐，当且仅当：
已缴已入账且覆盖午+晚的工单快照 deliver_dinner_with_lunch_snapshot=true，
或快照未置位但关联模版当前已勾选；
或台账导入等无全餐工单、但午餐+晚餐次数池都在、且本店在售全餐卡勾选一起配送。
默认 false，不改变纯午餐 / 分送全餐 / 纯晚餐。晚餐流水已送达则幂等跳过，不会扣两次。

本模块不得向午餐主路径抛业务异常，以免晚餐失败回滚午餐扣次。
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, CardOrderPayStatus, DeliveryStatus, MealPeriod
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.membership_card_template import MembershipCardTemplate
from app.services.meal_period.card_eligibility import meal_periods_from_snapshot_value
from app.services.meal_period.leave import is_absent_on_delivery_date_for_period
from app.services.meal_period.template_periods import normalize_meal_periods_list
from app.services.meal_period.units import effective_daily_meal_units_for_period

logger = logging.getLogger(__name__)

# 晚餐连带扣次流水备注，便于对账与幂等排查
_COMBO_WITH_LUNCH_DETAIL = "combo_with_lunch"


def coerce_deliver_dinner_with_lunch(periods: object, flag: bool | None) -> bool:
    """仅午+晚同时覆盖时允许「与午餐一起配送」；只勾午餐/只勾晚餐一律 false。"""
    ps = set(normalize_meal_periods_list(periods))
    if MealPeriod.LUNCH.value not in ps or MealPeriod.DINNER.value not in ps:
        return False
    return bool(flag)


def snapshot_deliver_dinner_with_lunch_from_template(
    template: MembershipCardTemplate | None,
    periods: object,
) -> bool:
    """入账快照：读模版开关并按餐段强制收敛。无模版（经典午餐卡）为 false。"""
    if template is None:
        return False
    return coerce_deliver_dinner_with_lunch(
        periods, bool(getattr(template, "deliver_dinner_with_lunch", False))
    )


def infer_combo_with_lunch_without_full_meal_order(
    *,
    has_paid_applied_order: bool,
    has_lunch_pool: bool,
    has_dinner_pool: bool,
    lunch_quota: int,
    dinner_quota: int,
    store_combo_meals_grants: frozenset[int] | set[int],
    store_has_active_combo_with_lunch: bool,
) -> bool:
    """无开卡工单时的导入全餐推断。

    已有任何已缴入账工单则不推断。
    午/晚累计总次数须相同，且等于本店在售「一起配送」全餐卡的入账份数（如 48），
    避免把午餐卡+晚餐残留或分购 24+24 当成全餐连带。
    """
    if has_paid_applied_order:
        return False
    if not has_lunch_pool or not has_dinner_pool:
        return False
    if not store_has_active_combo_with_lunch:
        return False
    lq = int(lunch_quota or 0)
    dq = int(dinner_quota or 0)
    if lq <= 0 or lq != dq:
        return False
    grants = {int(x) for x in store_combo_meals_grants if int(x) > 0}
    if not grants:
        return False
    return lq in grants


def _period_pool_active(balance: object, quota: object) -> bool:
    """该餐段次数池仍有效：剩余或累计总次数任一大于 0。"""
    return int(balance or 0) > 0 or int(quota or 0) > 0


def _store_active_combo_with_lunch_grants(db: Session, store_id: int) -> set[int]:
    """本店在售全餐卡（勾选与午餐一起配送）的入账份数。"""
    rows = db.execute(
        select(
            MembershipCardTemplate.meal_periods,
            MembershipCardTemplate.deliver_dinner_with_lunch,
            MembershipCardTemplate.meals_grant,
        ).where(
            MembershipCardTemplate.store_id == int(store_id),
            MembershipCardTemplate.is_active.is_(True),
        )
    ).all()
    grants: set[int] = set()
    for periods, flag, grant in rows:
        if coerce_deliver_dinner_with_lunch(periods, bool(flag)):
            g = int(grant or 0)
            if g > 0:
                grants.add(g)
    return grants


def _store_has_active_combo_with_lunch(db: Session, store_id: int) -> bool:
    """本店在售全餐卡是否勾选「与午餐一起配送」。"""
    return bool(_store_active_combo_with_lunch_grants(db, store_id))


def _legacy_import_combo_with_lunch(db: Session, member_id: int) -> bool:
    """台账导入无全餐工单：按次数池 + 本店全餐卡开关推断是否连带扣晚餐。"""
    member = db.get(Member, int(member_id))
    if member is None:
        return False
    dinner_row = db.get(
        MemberMealPeriodState,
        {"member_id": int(member_id), "meal_period": MealPeriod.DINNER.value},
    )
    dinner_bal = int(dinner_row.balance or 0) if dinner_row is not None else 0
    dinner_quota = int(dinner_row.meal_quota_total or 0) if dinner_row is not None else 0
    grants = _store_active_combo_with_lunch_grants(db, int(member.store_id))
    return infer_combo_with_lunch_without_full_meal_order(
        has_paid_applied_order=False,
        has_lunch_pool=_period_pool_active(member.balance, member.meal_quota_total),
        has_dinner_pool=_period_pool_active(dinner_bal, dinner_quota),
        lunch_quota=int(member.meal_quota_total or 0),
        dinner_quota=dinner_quota,
        store_combo_meals_grants=grants,
        store_has_active_combo_with_lunch=bool(grants),
    )


def member_has_combo_delivered_with_lunch(db: Session, member_id: int) -> bool:
    """是否应按「午餐送达同时扣晚餐」履约。

    已缴已入账且覆盖午+晚的工单：快照为 true 即命中（改模版为分开配送也不取消）；
    历史老会员快照默认 false 时，再看关联模版当前是否勾选一起配送。
    无任何已缴入账工单（台账导入全餐）时：午/晚累计总次数相同且等于本店全餐卡份数、并勾选一起配送，同样命中。
    """
    mid = int(member_id)
    rows = db.execute(
        select(
            MemberCardOrder.meal_periods_snapshot,
            MemberCardOrder.deliver_dinner_with_lunch_snapshot,
            MemberCardOrder.membership_template_id,
        ).where(
            MemberCardOrder.member_id == mid,
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
            MemberCardOrder.applied_to_member.is_(True),
        )
    ).all()
    template_ids: list[int] = []
    for snap, flag, tpl_id in rows:
        periods = meal_periods_from_snapshot_value(snap)
        if MealPeriod.LUNCH.value not in periods or MealPeriod.DINNER.value not in periods:
            continue
        if flag:
            return True
        if tpl_id is not None:
            template_ids.append(int(tpl_id))
    if template_ids:
        flags = db.scalars(
            select(MembershipCardTemplate.deliver_dinner_with_lunch).where(
                MembershipCardTemplate.id.in_(template_ids)
            )
        ).all()
        if any(bool(f) for f in flags):
            return True
        return False
    # 已有午餐卡/晚餐卡等非全餐工单：不把导入残留次数当成全餐连带
    if rows:
        return False
    return _legacy_import_combo_with_lunch(db, mid)


def try_apply_dinner_deduction_with_lunch(
    db: Session,
    member: Member,
    *,
    delivery_date: date,
    operator: str,
) -> bool:
    """
    午餐扣次已成功后的副作用：符合快照则追加扣晚餐并写晚餐送达流水。

    返回是否实际扣了晚餐。任何跳过/失败只打日志，不抛给午餐主路径。
    """
    try:
        return _apply_dinner_deduction_with_lunch_or_skip(
            db, member, delivery_date=delivery_date, operator=operator
        )
    except HTTPException as e:
        logger.warning(
            "全餐午餐连带扣晚餐跳过 member_id=%s date=%s detail=%s",
            getattr(member, "id", None),
            delivery_date,
            getattr(e, "detail", e),
        )
        return False
    except Exception:
        logger.exception(
            "全餐午餐连带扣晚餐异常，午餐扣次不受影响 member_id=%s date=%s",
            getattr(member, "id", None),
            delivery_date,
        )
        return False


def _apply_dinner_deduction_with_lunch_or_skip(
    db: Session,
    member: Member,
    *,
    delivery_date: date,
    operator: str,
) -> bool:
    if not member_has_combo_delivered_with_lunch(db, int(member.id)):
        return False

    d = delivery_date
    today = today_shanghai()
    if is_absent_on_delivery_date_for_period(
        db, member, d, meal_period=MealPeriod.DINNER.value, today=today
    ):
        logger.info(
            "全餐午餐连带扣晚餐跳过：当日晚餐请假 member_id=%s date=%s",
            member.id,
            d,
        )
        return False

    dinner_log = db.execute(
        select(DeliveryLog)
        .where(
            DeliveryLog.member_id == int(member.id),
            DeliveryLog.delivery_date == d,
            DeliveryLog.meal_period == MealPeriod.DINNER.value,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if dinner_log is not None and dinner_log.status == DeliveryStatus.DELIVERED.value:
        return False
    if dinner_log is not None and dinner_log.status == DeliveryStatus.LEAVE.value:
        logger.info(
            "全餐午餐连带扣晚餐跳过：晚餐流水为请假 member_id=%s date=%s",
            member.id,
            d,
        )
        return False

    deduct = effective_daily_meal_units_for_period(db, member, MealPeriod.DINNER.value)
    state_row = db.get(
        MemberMealPeriodState,
        {"member_id": int(member.id), "meal_period": MealPeriod.DINNER.value},
    )
    dinner_bal = max(0, int(state_row.balance or 0)) if state_row is not None else 0
    if dinner_bal < deduct:
        logger.warning(
            "全餐午餐连带扣晚餐跳过：晚餐次数不足 member_id=%s date=%s bal=%s need=%s",
            member.id,
            d,
            dinner_bal,
            deduct,
        )
        return False

    from app.services.meal_period.balance import deduct_dinner_balance

    if dinner_log is None:
        db.add(
            DeliveryLog(
                member_id=int(member.id),
                delivery_date=d,
                meal_period=MealPeriod.DINNER.value,
                status=DeliveryStatus.DELIVERED.value,
                courier_id=None,
            )
        )
    else:
        dinner_log.status = DeliveryStatus.DELIVERED.value
        dinner_log.courier_id = None

    deduct_dinner_balance(
        db,
        member,
        deduct=deduct,
        operator=(operator or "system").strip()[:50],
        reason=BalanceReason.DELIVERY,
        log_detail=_COMBO_WITH_LUNCH_DETAIL,
    )
    db.flush()
    return True
