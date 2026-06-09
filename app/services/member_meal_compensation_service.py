"""会员补餐赔付：餐品问题导致已消费次数需补回，并写入操作审计与余额流水。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive
from app.models.balance_log import BalanceLog
from app.models.enums import BalanceReason
from app.models.member import Member
from app.schemas.admin import MemberMealCompensationIn, MemberMealCompensationOut
from app.services.member_operation_log_service import OP_MEAL_COMPENSATION, record_member_operation
from app.services.member_renew_subscribe_service import reset_renew_remind_on_recharge
from app.services.single_meal_balance_pay_service import _maybe_reactivate_member_after_balance_restore


def admin_member_meal_compensation(
    db: Session,
    *,
    member_id: int,
    store_id: int,
    body: MemberMealCompensationIn,
    operator: str,
    ip_address: str | None = None,
) -> MemberMealCompensationOut:
    """为会员补回餐次：增加 balance、写入 balance_logs 与 member_operation_logs。"""
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

    remark = (body.remark or "").strip() or None
    balance_before = int(m.balance or 0)
    balance_after = balance_before + units

    m.balance = balance_after
    reset_renew_remind_on_recharge(m, balance_before=balance_before, balance_after=balance_after)
    _maybe_reactivate_member_after_balance_restore(m)

    detail_bits = [f"补餐{units}次"]
    if remark:
        detail_bits.append(remark[:480])
    log_detail = "；".join(detail_bits)

    db.add(
        BalanceLog(
            member_id=int(m.id),
            change=units,
            reason=BalanceReason.MEAL_COMPENSATION.value,
            operator=(operator or "admin")[:50],
            detail=log_detail[:500],
        )
    )
    db.add(m)

    summary = f"补餐 {units} 次"
    if remark:
        summary = f"{summary}；{remark[:120]}"

    record_member_operation(
        db,
        member_id=int(m.id),
        operation_type=OP_MEAL_COMPENSATION,
        summary=summary[:200],
        before={"balance": balance_before},
        after={"balance": balance_after, "meal_units": units, "remark": remark},
        ip_address=ip_address,
        source="admin",
        operator=operator,
    )

    now = beijing_now_naive()
    db.commit()
    db.refresh(m)

    return MemberMealCompensationOut(
        member_id=int(m.id),
        balance_before=balance_before,
        balance_after=int(m.balance or 0),
        meal_units=units,
        created_at=now.isoformat(),
    )
