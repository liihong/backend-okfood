"""会员补餐赔付：按餐段补回次数池，并写入操作审计与余额流水。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive
from app.models.balance_log import BalanceLog
from app.models.enums import BalanceReason, MealPeriod
from app.models.member import Member
from app.schemas.admin import MemberMealCompensationIn, MemberMealCompensationOut
from app.services.member.member_operation_log_service import OP_MEAL_COMPENSATION, record_member_operation
from app.services.member.member_renew_subscribe_service import reset_renew_remind_on_recharge
from app.services.client.single_meal_balance_pay_service import _maybe_reactivate_member_after_balance_restore


def _normalize_compensation_meal_period(raw: str | None) -> str:
    """补餐目标餐段：默认 lunch，与现网行为一致。"""
    p = (raw or MealPeriod.LUNCH.value).strip().lower()
    if p not in (MealPeriod.LUNCH.value, MealPeriod.DINNER.value):
        raise HTTPException(status_code=400, detail="meal_period 须为 lunch（午餐）或 dinner（晚餐）")
    return p


def admin_member_meal_compensation(
    db: Session,
    *,
    member_id: int,
    store_id: int,
    body: MemberMealCompensationIn,
    operator: str,
    ip_address: str | None = None,
) -> MemberMealCompensationOut:
    """为会员补回餐次：按餐段写入对应次数池、balance_logs 与 member_operation_logs。"""
    m = db.execute(
        select(Member).where(Member.id == int(member_id)).with_for_update()
    ).scalar_one_or_none()
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="会员不存在")
    if int(m.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="会员不存在")

    units = int(body.meal_units)
    if units < 1 or units > 50:
        raise HTTPException(status_code=400, detail="补餐份数须在 1～50 之间")

    period = _normalize_compensation_meal_period(getattr(body, "meal_period", None))
    remark = (body.remark or "").strip() or None

    if period == MealPeriod.DINNER.value:
        from app.services.meal_period.balance import apply_dinner_recharge_delta

        balance_before, balance_after = _apply_dinner_compensation(
            db,
            m,
            units=units,
            operator=operator,
            remark=remark,
        )
    else:
        balance_before, balance_after = _apply_lunch_compensation(
            db,
            m,
            units=units,
            operator=operator,
            remark=remark,
        )

    period_cn = "晚餐" if period == MealPeriod.DINNER.value else "午餐"
    summary = f"{period_cn}补餐 {units} 次"
    if remark:
        summary = f"{summary}；{remark[:120]}"

    record_member_operation(
        db,
        member_id=int(m.id),
        operation_type=OP_MEAL_COMPENSATION,
        summary=summary[:200],
        before={"balance": balance_before, "meal_period": period},
        after={"balance": balance_after, "meal_units": units, "meal_period": period, "remark": remark},
        ip_address=ip_address,
        source="admin",
        operator=operator,
    )

    now = beijing_now_naive()
    db.commit()
    db.refresh(m)

    return MemberMealCompensationOut(
        member_id=int(m.id),
        meal_period=period,
        balance_before=balance_before,
        balance_after=balance_after,
        meal_units=units,
        created_at=now.isoformat(),
    )


def _apply_lunch_compensation(
    db: Session,
    m: Member,
    *,
    units: int,
    operator: str,
    remark: str | None,
) -> tuple[int, int]:
    balance_before = int(m.balance or 0)
    balance_after = balance_before + units
    m.balance = balance_after
    reset_renew_remind_on_recharge(m, balance_before=balance_before, balance_after=balance_after)
    _maybe_reactivate_member_after_balance_restore(m)
    detail_bits = [f"补餐{units}次"]
    if remark:
        detail_bits.append(remark[:480])
    db.add(
        BalanceLog(
            member_id=int(m.id),
            meal_period=MealPeriod.LUNCH.value,
            change=units,
            reason=BalanceReason.MEAL_COMPENSATION.value,
            operator=(operator or "admin")[:50],
            detail="；".join(detail_bits)[:500],
        )
    )
    db.add(m)
    return balance_before, balance_after


def _apply_dinner_compensation(
    db: Session,
    m: Member,
    *,
    units: int,
    operator: str,
    remark: str | None,
) -> tuple[int, int]:
    from app.services.meal_period.balance import (
        dinner_balance_and_quota,
        ensure_dinner_period_state,
        sync_member_is_active_from_period_balances,
    )

    row = ensure_dinner_period_state(db, int(m.id))
    balance_before = int(row.balance or 0)
    balance_after = balance_before + units
    row.balance = balance_after
    db.add(row)
    detail_bits = [f"补餐{units}次"]
    if remark:
        detail_bits.append(remark[:480])
    db.add(
        BalanceLog(
            member_id=int(m.id),
            meal_period=MealPeriod.DINNER.value,
            change=units,
            reason=BalanceReason.MEAL_COMPENSATION.value,
            operator=(operator or "admin")[:50],
            detail="；".join(detail_bits)[:500],
        )
    )
    sync_member_is_active_from_period_balances(db, m)
    db.add(m)
    after, _ = dinner_balance_and_quota(row)
    return balance_before, after
