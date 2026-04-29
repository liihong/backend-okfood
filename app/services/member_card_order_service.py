from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import min_member_delivery_start_shanghai
from app.models.enums import CardOpenMode, CardOrderKind, CardOrderPayStatus, CardPayChannel, PlanType
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.schemas.admin import CardOrderCreateIn, CardOrderOut, CardOrderPatchIn, RechargeIn
from app.services.admin_service import apply_member_recharge_delta, _escape_like_fragment
from app.services.member_address_service import upsert_default_address_from_admin_map_pick
from app.services.store_config_service import get_member_card_prices_yuan

MINIPROGRAM_OFFLINE_CLAIM_ORDER_CREATOR = "miniprogram-offline"


def _quota_for_card_kind(kind: str) -> tuple[PlanType, int]:
    k = (kind or "").strip()
    if k == CardOrderKind.WEEK.value:
        return PlanType.WEEK, 6
    if k == CardOrderKind.MONTH.value:
        return PlanType.MONTH, 24
    if k == CardOrderKind.TIMES.value:
        return PlanType.TIMES, 1
    raise HTTPException(status_code=400, detail="无效开卡类型")


def _format_amount_yuan(v: Decimal | None) -> str | None:
    if v is None:
        return None
    return format(v, "f")


def _amount_yuan_for_card_kind_str(db: Session, card_kind: str) -> Decimal:
    k = (card_kind or "").strip()
    if k == CardOrderKind.WEEK.value:
        week_p, _ = get_member_card_prices_yuan(db)
        return week_p
    if k == CardOrderKind.MONTH.value:
        _, month_p = get_member_card_prices_yuan(db)
        return month_p
    if k == CardOrderKind.TIMES.value:
        return get_settings().MEMBER_CARD_TIMES_PRICE_YUAN
    raise HTTPException(status_code=400, detail="无效开卡类型")


def ensure_miniprogram_offline_claim_order(
    db: Session,
    member_id: int,
    *,
    card_kind: str,
    delivery_start_date: date,
) -> MemberCardOrder:
    """小程序端「已支付(线下)」：生成或更新一条未缴/渠道为线下的开卡工单，待后台标记已缴后同步入账。"""
    if delivery_start_date < min_member_delivery_start_shanghai():
        raise HTTPException(
            status_code=400,
            detail="起送日期须不早于允许的最小业务日（上海；当日 10:00 前最早今天，10:00 及之后最早明天）",
        )
    m = db.get(Member, member_id)
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if int(m.balance) > 0:
        raise HTTPException(status_code=400, detail="仅剩余次数为 0 时可登记线下开卡")
    k = (card_kind or "").strip()
    if k not in (CardOrderKind.WEEK.value, CardOrderKind.MONTH.value, CardOrderKind.TIMES.value):
        raise HTTPException(status_code=400, detail="开卡类型须为周卡、月卡或次卡")
    amt = _amount_yuan_for_card_kind_str(db, k)
    rmk = "小程序：用户自报已线下/其他方式缴费，待后台核对后标记已缴并同步入账"
    q = select(MemberCardOrder).where(
        MemberCardOrder.member_id == int(member_id),
        MemberCardOrder.pay_status == CardOrderPayStatus.UNPAID.value,
        MemberCardOrder.applied_to_member.is_(False),
        MemberCardOrder.pay_channel == CardPayChannel.OFFLINE.value,
        MemberCardOrder.created_by == MINIPROGRAM_OFFLINE_CLAIM_ORDER_CREATOR,
    )
    order = db.scalars(q.order_by(MemberCardOrder.id.desc()).limit(1)).first()
    if order is not None:
        order.card_kind = k
        order.delivery_start_date = delivery_start_date
        order.amount_yuan = amt
        order.remark = rmk
        order.out_trade_no = None
        order.wx_transaction_id = None
        db.flush()
        return order
    order = MemberCardOrder(
        member_id=int(member_id),
        card_kind=k,
        pay_channel=CardPayChannel.OFFLINE.value,
        pay_status=CardOrderPayStatus.UNPAID.value,
        amount_yuan=amt,
        remark=rmk,
        delivery_start_date=delivery_start_date,
        applied_to_member=False,
        out_trade_no=None,
        wx_transaction_id=None,
        created_by=MINIPROGRAM_OFFLINE_CLAIM_ORDER_CREATOR,
    )
    db.add(order)
    db.flush()
    return order


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
    """已缴且未入账：按卡型叠加次数/总配额；若工单有起送日则写入会员并激活，否则仅入账（暂不开卡）。"""
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
    id_bits: list[str] = []
    wn = (m.wechat_name or "").strip()
    if wn:
        id_bits.append(f"微信{wn[:100]}")
    ph = (m.phone or "").strip()
    if ph:
        id_bits.append(f"手机{ph}")
    if id_bits:
        parts.append("，".join(id_bits))
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
    if order.delivery_start_date is not None:
        m.is_active = True
        m.delivery_start_date = order.delivery_start_date
        m.delivery_deferred = False
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
    include_history: bool = False,
) -> tuple[list[CardOrderOut], int]:
    join_on = Member.id == MemberCardOrder.member_id
    filters = []
    if not include_history:
        # 默认工作台：隐藏「已缴且已同步入账」的完结单；其余（未缴、已缴待入账等）仍显示
        filters.append(
            or_(
                MemberCardOrder.pay_status != CardOrderPayStatus.PAID.value,
                MemberCardOrder.applied_to_member.is_(False),
            )
        )
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
    m = db.execute(select(Member).where(Member.phone == phone, Member.deleted_at.is_(None))).scalar_one_or_none()
    if not m:
        if body.open_mode == CardOpenMode.RENEW:
            raise HTTPException(status_code=404, detail="会员不存在")
        nm = (body.name or "").strip()
        if not nm:
            raise HTTPException(status_code=400, detail="新会员开卡须填写会员姓名")
        wx_raw = (body.wechat_name or "").strip()
        m = Member(
            phone=phone[:20],
            name=nm[:100],
            wechat_name=wx_raw[:100] if wx_raw else None,
            remarks=None,
            avatar_url=None,
            balance=0,
            daily_meal_units=1,
            meal_quota_total=0,
            plan_type=None,
            is_active=False,
            is_leaved_tomorrow=False,
            leave_range_start=None,
            leave_range_end=None,
            wx_mini_openid=None,
        )
        db.add(m)
        db.flush()
    elif body.open_mode == CardOpenMode.NEW_MEMBER:
        # 仅「新会员开卡」写入姓名/微信；老会员续卡只认手机号，不覆盖档案
        if body.name is not None:
            nm = body.name.strip()
            if nm:
                m.name = nm[:100]
        if body.wechat_name is not None:
            wx = body.wechat_name.strip()
            m.wechat_name = wx[:100] if wx else None
    if body.delivery_start_date is not None:
        if body.delivery_start_date < min_member_delivery_start_shanghai():
            raise HTTPException(
                status_code=400,
                detail="起送日期须不早于允许的最小业务日（上海；当日 10:00 前最早今天，10:00 及之后最早明天）",
            )
    if body.delivery_address is not None:
        da = body.delivery_address
        cphone = (da.contact_phone or "").strip() or phone
        upsert_default_address_from_admin_map_pick(
            db,
            member_id=m.id,
            contact_name=(m.name or "").strip() or phone[:20],
            contact_phone=cphone[:20],
            map_location_text=da.map_location_text,
            door_detail=da.door_detail,
            lng=float(da.lng),
            lat=float(da.lat),
        )
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
    # 已缴即入账：与是否传 sync_member 无关（避免勾选遗漏导致剩余次数仍为 0）
    if body.pay_status == CardOrderPayStatus.PAID:
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
    patch.pop("sync_member", None)
    updating_card_kind = "card_kind" in body.model_fields_set
    if updating_card_kind:
        patch.pop("card_kind", None)
        if order.applied_to_member:
            raise HTTPException(status_code=400, detail="已入账的工单不可修改卡类型")
        if body.card_kind is None:
            raise HTTPException(status_code=400, detail="卡类型无效")
        order.card_kind = body.card_kind.value

    if not patch and not updating_card_kind:
        if not (
            order.pay_status == CardOrderPayStatus.PAID.value and not order.applied_to_member
        ):
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
        ds = body.delivery_start_date
        if ds is not None and ds < min_member_delivery_start_shanghai():
            raise HTTPException(
                status_code=400,
                detail="起送日期须不早于允许的最小业务日（上海；当日 10:00 前最早今天，10:00 及之后最早明天）",
            )
        order.delivery_start_date = ds
        if order.applied_to_member:
            mem = db.get(Member, order.member_id)
            if mem:
                mem.delivery_start_date = order.delivery_start_date

    db.flush()
    if order.pay_status == CardOrderPayStatus.PAID.value and not order.applied_to_member:
        _sync_order_to_member(db, order, operator=operator)

    db.commit()
    db.refresh(order)
    return _order_to_out(db, order)
