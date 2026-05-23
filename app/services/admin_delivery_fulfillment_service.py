"""管理端代标记：配送到家 / 门店自提「订阅日」扣次 + delivery_logs，不产生骑手待结算。"""

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.timeutil import today_shanghai
from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, DeliveryStatus
from app.models.member import Member
from app.services.courier_service import eligible_members_for_delivery, eligible_members_for_store_pickup
from app.services.leave import is_absent_on_delivery_date
from app.services.member_service import effective_daily_meal_units


def _eligible_ids_home(db: Session, d: date, *, store_id: int) -> set[int]:
    members, _ = eligible_members_for_delivery(
        db, delivery_date=d, delivery_region_id=None, store_id=int(store_id)
    )
    return {int(m.id) for m in members}


def _eligible_ids_pickup(db: Session, d: date, *, store_id: int) -> set[int]:
    members, _ = eligible_members_for_store_pickup(db, delivery_date=d, store_id=int(store_id))
    return {int(m.id) for m in members}


def _subscription_fulfilled_apply(
    db: Session,
    *,
    member_id: int,
    delivery_date: date,
    operator_tag: str,
    kind: str,
    ok_ids: set[int],
) -> None:
    """与 ``admin_mark_subscription_fulfilled`` 相同业务规则；不落库事务（由调用方 commit）。"""
    if kind not in ("home", "pickup"):
        raise HTTPException(status_code=400, detail="类型无效")
    d = delivery_date
    today = today_shanghai()
    if int(member_id) not in ok_ids:
        raise HTTPException(
            status_code=400,
            detail="该会员不在当日大表名单内或不符合条件（请假/余额/起送日/非配送日等）",
        )

    member = db.execute(select(Member).where(Member.id == member_id).with_for_update()).scalar_one_or_none()
    if not member or member.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if bool(member.store_pickup) != (kind == "pickup"):
        raise HTTPException(
            status_code=400,
            detail="会员履约方式与标记类型不一致",
        )

    deduct = effective_daily_meal_units(member)
    if not member.is_active or member.balance <= 0:
        raise HTTPException(status_code=400, detail="用户未激活或次数不足")
    if member.balance < deduct:
        raise HTTPException(status_code=400, detail="次数不足，无法满足当日份数扣减")
    if is_absent_on_delivery_date(member, d, today=today):
        raise HTTPException(status_code=400, detail="该日用户请假，无法确认")
    if member.delivery_start_date is not None and d < member.delivery_start_date:
        raise HTTPException(status_code=400, detail="未到约定的开始配送日，无法确认")
    if not is_subscription_delivery_day(d):
        raise HTTPException(status_code=400, detail="该日为周日或法定节假日，订阅配送不履约")

    log = db.execute(
        select(DeliveryLog).where(DeliveryLog.member_id == member_id, DeliveryLog.delivery_date == d).with_for_update()
    ).scalar_one_or_none()

    if log and log.status == DeliveryStatus.DELIVERED.value:
        return
    if log and log.status == DeliveryStatus.LEAVE.value:
        raise HTTPException(status_code=400, detail="该日记录为请假状态")

    op_tag = (operator_tag or "admin:unknown").strip()[:50]

    if not log:
        log = DeliveryLog(
            member_id=member_id, delivery_date=d, status=DeliveryStatus.DELIVERED.value, courier_id=None
        )
        db.add(log)
    else:
        log.status = DeliveryStatus.DELIVERED.value
        log.courier_id = None

    member.balance -= deduct
    balance_before = int(member.balance) + int(deduct)
    if member.balance <= 0:
        member.is_active = False
    db.add(
        BalanceLog(
            member_id=member_id,
            change=-deduct,
            reason=BalanceReason.DELIVERY.value,
            operator=op_tag,
            detail=None,
        )
    )
    from app.services.member_renew_subscribe_service import try_send_renew_remind_after_balance_change

    try_send_renew_remind_after_balance_change(db, member, balance_before=balance_before)


def admin_mark_subscription_fulfilled(
    db: Session,
    *,
    member_id: int,
    delivery_date: date,
    admin_username: str,
    kind: str,
    store_id: int,
) -> None:
    """
    kind: ``"home"`` 配送到家 / ``"pickup"`` 门店自提。
    与骑手端确认一致的业务校验（除片区外）；已送达则幂等；不增加 courier.fee_pending。
    """
    d = delivery_date
    if kind == "home":
        ok_ids = _eligible_ids_home(db, d, store_id=int(store_id))
    else:
        ok_ids = _eligible_ids_pickup(db, d, store_id=int(store_id))
    op = (admin_username or "admin").strip()[:44]
    op_tag = f"admin:{op}"[:50]
    _subscription_fulfilled_apply(
        db,
        member_id=member_id,
        delivery_date=d,
        operator_tag=op_tag,
        kind=kind,
        ok_ids=ok_ids,
    )
    db.commit()


def subscription_fulfilled_try_sf_home_no_commit(
    db: Session,
    *,
    member_id: int,
    delivery_date: date,
    operator_tag: str = "sf:order_complete",
    store_id: int | None = None,
    extra_ok_member_ids: set[int] | frozenset[int] | None = None,
) -> None:
    """
    顺丰自动履约（到家）：与智能配送大表标记送达口径一致；
    operator 默认为 ``sf:order_complete``（订单完成）；配送状态推送妥投为 ``sf:delivery_status``；不产生独立 commit。

    ``extra_ok_member_ids``：推单快照中已锁定的会员，即使当前 SQL 应送名单未命中也允许扣次（顺丰已妥投）。
    """
    d = delivery_date
    from app.core.config import get_settings

    sid = int(store_id) if store_id is not None else int(get_settings().DEFAULT_STORE_ID)
    ok_ids = _eligible_ids_home(db, d, store_id=sid)
    if extra_ok_member_ids:
        ok_ids = set(ok_ids) | {int(x) for x in extra_ok_member_ids}
    tag = (operator_tag or "sf:order_complete").strip()[:50] or "sf:order_complete"
    _subscription_fulfilled_apply(
        db,
        member_id=member_id,
        delivery_date=d,
        operator_tag=tag,
        kind="home",
        ok_ids=ok_ids,
    )
