from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.enums import CardOpenMode, CardOrderKind, CardOrderPayStatus, PlanType
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.schemas.admin import CardOrderCreateIn, CardOrderOut, CardOrderPatchIn, RechargeIn
from app.services.admin_service import apply_member_recharge_delta, _escape_like_fragment


def _quota_for_card_kind(kind: str) -> tuple[PlanType, int]:
    k = (kind or "").strip()
    if k == CardOrderKind.WEEK.value:
        return PlanType.WEEK, 6
    if k == CardOrderKind.MONTH.value:
        return PlanType.MONTH, 24
    raise HTTPException(status_code=400, detail="无效开卡类型")


def _format_amount_yuan(v: Decimal | None) -> str | None:
    if v is None:
        return None
    return format(v, "f")


def _order_to_out(db: Session, order: MemberCardOrder) -> CardOrderOut:
    m = db.get(Member, order.member_id)
    name = (m.name if m else "") or ""
    phone = (m.phone if m else "") or ""
    ca = order.created_at.isoformat() if order.created_at else ""
    ua = order.updated_at.isoformat() if order.updated_at else ""
    ds = order.delivery_start_date.isoformat() if order.delivery_start_date else None
    wn = (m.wechat_name if m else None) or None
    if wn is not None:
        wn = str(wn).strip() or None
    return CardOrderOut(
        id=int(order.id),
        member_id=int(order.member_id),
        member_phone=phone,
        member_name=name,
        member_wechat_name=wn,
        delivery_start_date=ds,
        card_kind=order.card_kind,
        pay_channel=order.pay_channel,
        pay_status=order.pay_status,
        amount_yuan=_format_amount_yuan(order.amount_yuan),
        remark=order.remark,
        applied_to_member=bool(order.applied_to_member),
        created_by=order.created_by,
        created_at=ca,
        updated_at=ua,
    )


def _apply_paid_card_order_to_member_balance(db: Session, order: MemberCardOrder, *, operator: str) -> None:
    """已缴且未入账：按卡型叠加次数/总配额并更新起送日（幂等由调用方保证）。"""
    m = db.get(Member, order.member_id)
    if not m:
        raise HTTPException(status_code=404, detail="会员不存在")
    plan, amt = _quota_for_card_kind(order.card_kind)
    parts = [
        f"开卡工单#{order.id}",
        f"{order.card_kind}",
        f"同步入账+{amt}次",
        f"渠道{order.pay_channel}",
    ]
    ay = _format_amount_yuan(order.amount_yuan)
    if ay is not None:
        parts.append(f"实收{ay}元")
    rmk = (order.remark or "").strip()
    if rmk:
        parts.append(f"备注{rmk[:180]}")
    log_detail = "；".join(parts)
    apply_member_recharge_delta(
        db,
        RechargeIn(phone=m.phone, amount=amt, plan_type=plan),
        operator=operator,
        log_detail=log_detail,
    )
    start = order.delivery_start_date or today_shanghai()
    if order.delivery_start_date is None:
        order.delivery_start_date = start
    m.is_active = True
    m.delivery_start_date = start
    order.applied_to_member = True


def apply_paid_card_order_to_member_if_pending(db: Session, order: MemberCardOrder, *, operator: str) -> None:
    """支付回调等场景：仅当已缴且未入账时入账（可重复调用）。"""
    if order.applied_to_member:
        return
    if order.pay_status != CardOrderPayStatus.PAID.value:
        return
    _apply_paid_card_order_to_member_balance(db, order, operator=operator)


def _sync_order_to_member(db: Session, order: MemberCardOrder, *, operator: str) -> None:
    if order.applied_to_member:
        raise HTTPException(status_code=400, detail="该工单已入账，请勿重复同步")
    if order.pay_status != CardOrderPayStatus.PAID.value:
        raise HTTPException(status_code=400, detail="仅「已缴」工单可同步会员次数")
    _apply_paid_card_order_to_member_balance(db, order, operator=operator)


def list_card_orders_paged(
    db: Session,
    *,
    q: str | None,
    pay_status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[CardOrderOut], int]:
    join_on = Member.id == MemberCardOrder.member_id
    filters = []
    if q and q.strip():
        esc = _escape_like_fragment(q.strip())
        filters.append(
            or_(
                Member.phone.like(f"{esc}%", escape="\\"),
                Member.name.like(f"%{esc}%", escape="\\"),
                Member.wechat_name.like(f"%{esc}%", escape="\\"),
            )
        )
    ps = (pay_status or "").strip()
    if ps in (CardOrderPayStatus.UNPAID.value, CardOrderPayStatus.PAID.value):
        filters.append(MemberCardOrder.pay_status == ps)

    count_stmt = select(func.count()).select_from(MemberCardOrder).join(Member, join_on)
    for f in filters:
        count_stmt = count_stmt.where(f)
    total = int(db.scalar(count_stmt) or 0)

    list_stmt = (
        select(MemberCardOrder)
        .join(Member, join_on)
        .order_by(MemberCardOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    for f in filters:
        list_stmt = list_stmt.where(f)
    rows = db.scalars(list_stmt).all()
    return [_order_to_out(db, r) for r in rows], total


def create_card_order(db: Session, body: CardOrderCreateIn, *, operator: str) -> CardOrderOut:
    phone = body.phone.strip()
    m = db.execute(select(Member).where(Member.phone == phone)).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="会员不存在")
    # 仅「新会员开卡」写入姓名/微信；老会员续卡只认手机号，不覆盖档案
    if body.open_mode == CardOpenMode.NEW_MEMBER:
        if body.name is not None:
            nm = body.name.strip()
            if nm:
                m.name = nm[:100]
        if body.wechat_name is not None:
            wx = body.wechat_name.strip()
            m.wechat_name = wx[:100] if wx else None
    order = MemberCardOrder(
        member_id=m.id,
        card_kind=body.card_kind.value,
        pay_channel=body.pay_channel.value,
        pay_status=body.pay_status.value,
        amount_yuan=body.amount_yuan,
        remark=body.remark,
        delivery_start_date=body.delivery_start_date,
        created_by=operator,
    )
    db.add(order)
    db.flush()
    if body.pay_status == CardOrderPayStatus.PAID and body.sync_member:
        _sync_order_to_member(db, order, operator=operator)
    db.commit()
    db.refresh(order)
    return _order_to_out(db, order)


def update_card_order(
    db: Session, order_id: int, body: CardOrderPatchIn, *, operator: str
) -> CardOrderOut:
    order = db.get(MemberCardOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    patch = body.model_dump(exclude_unset=True)
    sync_flag = bool(patch.pop("sync_member", False))
    updating_card_kind = "card_kind" in body.model_fields_set
    if updating_card_kind:
        patch.pop("card_kind", None)
        if order.applied_to_member:
            raise HTTPException(status_code=400, detail="已入账的工单不可修改卡类型")
        if body.card_kind is None:
            raise HTTPException(status_code=400, detail="卡类型无效")
        order.card_kind = body.card_kind.value

    if not patch and not sync_flag and not updating_card_kind:
        raise HTTPException(status_code=400, detail="请至少提交一项修改")

    if "pay_status" in patch and body.pay_status is not None:
        if order.applied_to_member and body.pay_status == CardOrderPayStatus.UNPAID:
            raise HTTPException(status_code=400, detail="已入账的工单不可改回未缴")
        order.pay_status = body.pay_status.value

    if "pay_channel" in patch and body.pay_channel is not None:
        order.pay_channel = body.pay_channel.value

    if "amount_yuan" in patch:
        order.amount_yuan = body.amount_yuan

    if "remark" in patch:
        order.remark = body.remark

    if "delivery_start_date" in patch:
        order.delivery_start_date = body.delivery_start_date
        if order.applied_to_member:
            mem = db.get(Member, order.member_id)
            if mem:
                mem.delivery_start_date = order.delivery_start_date

    db.flush()
    if sync_flag and order.pay_status == CardOrderPayStatus.PAID.value and not order.applied_to_member:
        _sync_order_to_member(db, order, operator=operator)

    db.commit()
    db.refresh(order)
    return _order_to_out(db, order)
