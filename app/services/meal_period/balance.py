"""分餐段次数池：午餐仍用 members 表；晚餐读写 member_meal_period_state。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.balance_log import BalanceLog
from app.models.enums import BalanceReason, MealPeriod, PlanType
from app.models.member import Member
from app.models.member_meal_period_state import MemberMealPeriodState


def _truncate_detail(detail: str | None) -> str | None:
    d = (detail or "").strip() or None
    if d and len(d) > 500:
        return d[:500]
    return d


def ensure_dinner_period_state(db: Session, member_id: int) -> MemberMealPeriodState:
    """确保晚餐运营态行存在（默认份数 1、次数 0）。"""
    mid = int(member_id)
    row = db.get(
        MemberMealPeriodState,
        {"member_id": mid, "meal_period": MealPeriod.DINNER.value},
    )
    if row is not None:
        return row
    row = MemberMealPeriodState(
        member_id=mid,
        meal_period=MealPeriod.DINNER.value,
        daily_meal_units=1,
        balance=0,
        meal_quota_total=0,
    )
    db.add(row)
    db.flush()
    return row


def dinner_balance_and_quota(row: MemberMealPeriodState | None) -> tuple[int, int]:
    """晚餐剩余/总次数；无行时均为 0。"""
    if row is None:
        return 0, 0
    bal = max(0, int(row.balance or 0))
    quota = max(0, int(row.meal_quota_total or 0))
    if quota <= 0:
        quota = bal
    return bal, quota


def balance_quota_for_sheet_period(
    member: Member,
    *,
    meal_period: str,
    state_row: MemberMealPeriodState | None = None,
) -> tuple[int, int]:
    """大表展示：午餐读 members；晚餐读 member_meal_period_state。"""
    period = (meal_period or MealPeriod.LUNCH.value).strip().lower()
    if period == MealPeriod.DINNER.value:
        return dinner_balance_and_quota(state_row)
    bal = max(0, int(member.balance or 0))
    quota = max(0, int(getattr(member, "meal_quota_total", 0) or 0))
    if quota <= 0:
        quota = bal
    return bal, quota


def member_has_any_period_balance(db: Session, member: Member) -> bool:
    """任一餐段有余次即视为已开卡（午餐读 members.balance，晚餐读 member_meal_period_state）。"""
    if int(member.balance or 0) > 0:
        return True
    dinner_row = db.get(
        MemberMealPeriodState,
        {"member_id": int(member.id), "meal_period": MealPeriod.DINNER.value},
    )
    return dinner_row is not None and int(dinner_row.balance or 0) > 0


def sync_member_is_active_from_period_balances(db: Session, member: Member) -> None:
    """
    激活态由「已起送且未暂停」+「任一餐段有余次」共同决定。
    午餐扣至 0 但晚餐仍有余次时保持激活；反之亦然。
    """
    lunch_bal = max(0, int(member.balance or 0))
    dinner_row = db.get(
        MemberMealPeriodState,
        {"member_id": int(member.id), "meal_period": MealPeriod.DINNER.value},
    )
    dinner_bal = max(0, int(dinner_row.balance or 0)) if dinner_row else 0
    any_balance = lunch_bal > 0 or dinner_bal > 0
    if not any_balance:
        member.is_active = False
        return
    if member.delivery_start_date is not None and not bool(member.delivery_deferred):
        member.is_active = True


def apply_dinner_recharge_delta(
    db: Session,
    member: Member,
    *,
    amount: int,
    plan_type: PlanType | None = None,
    bump_meal_quota_total: bool = False,
    operator: str,
    log_detail: str | None = None,
) -> int:
    """调整晚餐剩余次数并写 balance_logs（meal_period=dinner）；返回变更前余额。"""
    if amount == 0:
        raise HTTPException(status_code=400, detail="调整幅度不能为 0")
    row = ensure_dinner_period_state(db, int(member.id))
    balance_before = int(row.balance or 0)
    row.balance = balance_before + int(amount)
    if row.balance < 0:
        raise HTTPException(status_code=400, detail="晚餐次数不足，无法扣减到负数")
    if plan_type is not None and amount > 0:
        member.plan_type = plan_type.value
    if amount > 0 and plan_type is not None:
        bump_q = plan_type in (PlanType.WEEK, PlanType.MONTH) or bool(bump_meal_quota_total)
        if bump_q:
            row.meal_quota_total = int(row.meal_quota_total or 0) + int(amount)
    db.add(row)
    db.add(
        BalanceLog(
            member_id=int(member.id),
            meal_period=MealPeriod.DINNER.value,
            change=int(amount),
            reason=BalanceReason.RECHARGE.value if amount > 0 else BalanceReason.REFUND.value,
            operator=operator,
            detail=_truncate_detail(log_detail),
        )
    )
    sync_member_is_active_from_period_balances(db, member)
    return balance_before


def deduct_dinner_balance(
    db: Session,
    member: Member,
    *,
    deduct: int,
    operator: str,
    reason: BalanceReason = BalanceReason.DELIVERY,
    log_detail: str | None = None,
) -> int:
    """晚餐送达扣次；返回扣次前余额。"""
    units = max(1, int(deduct))
    row = ensure_dinner_period_state(db, int(member.id))
    bal = int(row.balance or 0)
    if bal < units:
        raise HTTPException(status_code=400, detail="晚餐次数不足，无法满足当日份数扣减")
    row.balance = bal - units
    db.add(row)
    db.add(
        BalanceLog(
            member_id=int(member.id),
            meal_period=MealPeriod.DINNER.value,
            change=-units,
            reason=reason.value,
            operator=(operator or "system").strip()[:50],
            detail=_truncate_detail(log_detail),
        )
    )
    sync_member_is_active_from_period_balances(db, member)
    return bal


def reset_dinner_quota_on_membership_reopen(db: Session, member_id: int) -> None:
    """退卡后重新开卡：清零晚餐总次数分母（与 members.meal_quota_total 对齐）。"""
    row = db.get(
        MemberMealPeriodState,
        {"member_id": int(member_id), "meal_period": MealPeriod.DINNER.value},
    )
    if row is not None:
        row.meal_quota_total = 0
        db.add(row)
