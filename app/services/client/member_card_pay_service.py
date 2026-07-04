"""小程序自助开卡/续卡：创建工单、微信 JSAPI 预下单、支付回调入账。"""

from __future__ import annotations

import logging
import secrets
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, DataError, IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive, min_member_delivery_start_shanghai
from app.core.config import get_settings
from app.integrations.wechat_pay_v2 import (
    WeChatPayV2Error,
    WechatPayNotifyParsed,
    build_miniprogram_pay_params,
    close_order_by_out_trade_no,
    query_order_by_out_trade_no,
    refund_order_v2,
    unified_order_jsapi,
    yuan_decimal_to_fen,
)
from app.services.shared.tenant_integration_service import (
    get_merged_pay_config,
    wechat_pay_misconfiguration_detail_merged,
)
from app.models.enums import CardOrderKind, CardOrderPayStatus, CardPayChannel, CouponLockedOrderBiz
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_coupon import MemberCoupon
from app.models.marketing_coupon_template import MarketingCouponTemplate
from app.models.membership_card_template import MembershipCardTemplate
from app.services.admin.catalog_admin_service import get_membership_template_row
from app.services.admin.admin_system_notification_service import (
    create_miniprogram_card_order_pending_notification,
)
from app.services.member.member_card_order_service import (
    apply_paid_card_order_to_member_if_pending,
    enum_card_kind_for_template,
    revoke_paid_card_order_member_sync,
)
from app.services.shared.store_config_service import get_member_card_prices_yuan
from app.services.marketing.coupon_checkout_service import (
    CouponCheckoutContext,
    lock_member_coupon_for_order,
    mark_member_coupon_used_for_order,
    release_member_coupon_for_order,
)

logger = logging.getLogger(__name__)

# 与单次零售未支付单一致：超时释放 locked 券并恢复订单原价
UNPAID_MINIPROGRAM_CARD_ORDER_EXPIRE_MINUTES = 30
MINIPROGRAM_WECHAT_ORDER_CREATOR = "miniprogram"
# 旧库 pay_status ENUM 无「已取消」时，用 created_by 标记取消（见 migration_037）
MINIPROGRAM_WECHAT_ORDER_CANCELLED_CREATOR = "miniprogram:cancelled"
_MEMBER_CARD_CANCEL_REMARK_TAG = "[会员已取消]"


def _new_temp_out_trade_no() -> str:
    return f"T{secrets.token_hex(14)}"[:32]


def _final_out_trade_no(order_id: int) -> str:
    s = f"OKC{order_id}"
    if len(s) > 32:
        raise HTTPException(status_code=500, detail="开卡订单号超长")
    return s


def _rotated_member_card_out_trade_no(order_id: int) -> str:
    """换券/改价后须换新商户单号，避免微信「重入参数不一致」。"""
    suffix = secrets.token_hex(3).upper()
    return f"OKC{int(order_id)}{suffix}"[:32]


def _is_wechat_unified_reentry_mismatch(message: str) -> bool:
    """微信统一下单：同一 out_trade_no 重入但 body/金额/openid 等与首次不一致。"""
    m = (message or "").strip()
    return "请求重入" in m or "参数与首次请求时不一致" in m


def _close_wechat_order_best_effort(out_trade_no: str, *, pay: object) -> None:
    """关单失败（如订单不存在）时忽略，不阻断后续轮换商户单号。"""
    otn = (out_trade_no or "").strip()
    if not otn:
        return
    try:
        close_order_by_out_trade_no(otn, pay=pay)
    except WeChatPayV2Error as e:
        logger.info("微信关单（可忽略） out=%s err=%s", otn, e)


def _rotate_member_card_order_out_trade_no(
    db: Session,
    order: MemberCardOrder,
    *,
    pay: object,
    commit: bool = True,
) -> str:
    """关闭微信侧旧单并写入新商户单号（本地工单 id 不变）。"""
    old = (order.out_trade_no or "").strip()
    if old:
        _close_wechat_order_best_effort(old, pay=pay)
    new_no = _rotated_member_card_out_trade_no(int(order.id))
    order.out_trade_no = new_no
    if commit:
        db.commit()
        db.refresh(order)
    logger.info(
        "开卡工单轮换商户单号 order_id=%s old=%s new=%s",
        int(order.id),
        old,
        new_no,
    )
    return new_no


def _member_card_order_body_desc(db: Session, order: MemberCardOrder) -> str:
    """统一下单商品描述（与首次下单保持一致，减少重入不一致）。"""
    tid = getattr(order, "membership_template_id", None)
    kind_label = (order.card_kind or "").strip() or "套卡"
    body_desc = f"会员{kind_label}开卡"
    if tid:
        tpl = db.get(MembershipCardTemplate, int(tid))
        if tpl:
            nm = (tpl.name or "").strip() or kind_label
            body_desc = f"OK饭自律卡·{nm}"
            if len(body_desc) > 42:
                body_desc = body_desc[:42]
    return body_desc


def _reconcile_wechat_out_trade_no_before_card_prepay(
    db: Session,
    order: MemberCardOrder,
    *,
    pay: object,
) -> None:
    """
    统一下单前对齐微信侧状态：已支付则拉单入账；未支付但金额与本地不一致则关单并轮换商户单号。
    """
    out_no = (order.out_trade_no or "").strip()
    if not out_no:
        return
    try:
        data = query_order_by_out_trade_no(out_no, pay=pay)
    except WeChatPayV2Error:
        return

    if (data.get("result_code") or "").upper() != "SUCCESS":
        err_c = (data.get("err_code") or "").strip().upper()
        if err_c == "ORDERNOTEXIST":
            return
        return

    ts = (data.get("trade_state") or "").strip().upper()
    if ts == "SUCCESS":
        sync_member_card_from_wechat_or_raise(db, int(order.member_id), int(order.id))
        raise HTTPException(status_code=400, detail="订单已支付，请下拉刷新")
    if ts == "USERPAYING":
        raise HTTPException(status_code=400, detail="微信侧支付处理中，请稍候再试")
    if ts == "CLOSED":
        return

    if ts not in ("NOTPAY", ""):
        return

    try:
        wx_fee = int((data.get("total_fee") or "0").strip() or 0)
    except ValueError:
        wx_fee = -1
    expect_fee = yuan_decimal_to_fen(order.amount_yuan)
    if wx_fee >= 0 and wx_fee != expect_fee:
        _rotate_member_card_order_out_trade_no(db, order, pay=pay)


def _unified_order_jsapi_for_member_card_order(
    db: Session,
    order: MemberCardOrder,
    *,
    body_desc: str,
    openid: str,
    client_ip: str,
    pay: object,
) -> str:
    """统一下单；遇微信重入参数不一致时关单轮换商户单号并重试一次。"""
    out_no = (order.out_trade_no or "").strip()
    if not out_no:
        raise HTTPException(status_code=500, detail="订单缺少商户单号")
    total_fee_fen = yuan_decimal_to_fen(order.amount_yuan)
    last_err: WeChatPayV2Error | None = None
    for attempt in range(2):
        try:
            return unified_order_jsapi(
                out_trade_no=out_no,
                body=body_desc,
                total_fee_fen=total_fee_fen,
                openid=openid,
                spbill_create_ip=client_ip,
                pay=pay,
            )
        except WeChatPayV2Error as e:
            last_err = e
            if attempt == 0 and _is_wechat_unified_reentry_mismatch(str(e)):
                out_no = _rotate_member_card_order_out_trade_no(db, order, pay=pay)
                continue
            raise
    if last_err is not None:
        raise last_err
    raise WeChatPayV2Error(502, "微信统一下单失败")


def _format_amount_yuan(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01')):.2f}"


def _is_member_self_service_renewal(db: Session, member: Member) -> bool:
    """老用户自主购卡续费：曾有过入账权益、仍有剩余次数或已约定起送日。"""
    if int(member.balance or 0) > 0:
        return True
    if int(member.meal_quota_total or 0) > 0:
        return True
    if member.delivery_start_date is not None:
        return True
    paid_count = db.scalar(
        select(func.count())
        .select_from(MemberCardOrder)
        .where(
            MemberCardOrder.member_id == int(member.id),
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
        )
    )
    return int(paid_count or 0) > 0


def _miniprogram_card_order_remark(base: str | None, *, is_renewal: bool) -> str | None:
    """小程序开卡工单备注：续卡时前缀「老会员续卡」。"""
    b = (base or "").strip()
    if is_renewal:
        prefix = "老会员续卡"
        return f"{prefix}·{b}"[:500] if b else prefix
    return b or None


# 备注中优惠券段落前缀，便于换券/释券时剥离
_CARD_ORDER_COUPON_REMARK_MARKER = "·优惠券"


def _strip_coupon_from_card_order_remark(remark: str | None) -> str:
    """移除备注末尾的优惠券说明（换券或取消用券时）。"""
    r = (remark or "").strip()
    idx = r.find(_CARD_ORDER_COUPON_REMARK_MARKER)
    if idx >= 0:
        return r[:idx].strip()
    return r


def _coupon_remark_segment(
    db: Session, *, member_coupon_id: int, discount_yuan: Decimal
) -> str:
    """生成可追加到开卡工单备注的优惠券摘要。"""
    disc = _format_amount_yuan(discount_yuan)
    coupon = db.get(MemberCoupon, int(member_coupon_id))
    tpl_name = ""
    if coupon is not None:
        tpl = db.get(MarketingCouponTemplate, int(coupon.template_id))
        if tpl is not None:
            tpl_name = (tpl.name or "").strip()
    name_part = f"「{tpl_name}」" if tpl_name else ""
    return f"{_CARD_ORDER_COUPON_REMARK_MARKER}{name_part}减{disc}元(用户券#{int(member_coupon_id)})"


def _apply_coupon_to_card_order_remark(
    db: Session,
    order: MemberCardOrder,
    *,
    member_coupon_id: int,
    discount_yuan: Decimal,
) -> None:
    """锁券成功后写入/更新备注中的优惠券信息。"""
    base = _strip_coupon_from_card_order_remark(order.remark)
    seg = _coupon_remark_segment(
        db, member_coupon_id=int(member_coupon_id), discount_yuan=discount_yuan
    )
    combined = f"{base}{seg}" if base else seg.lstrip("·")
    order.remark = combined[:500] if combined else None


def _clear_coupon_from_card_order_remark(order: MemberCardOrder) -> None:
    """释券后恢复不含优惠券段落的备注。"""
    stripped = _strip_coupon_from_card_order_remark(order.remark)
    order.remark = stripped or None


def card_order_amount_yuan_for_kind(db: Session, card_kind: str, *, store_id: int | None = None) -> Decimal:
    k = (card_kind or "").strip()
    if k == CardOrderKind.WEEK.value:
        week_p, _ = get_member_card_prices_yuan(db, store_id=store_id)
        return week_p
    if k == CardOrderKind.MONTH.value:
        _, month_p = get_member_card_prices_yuan(db, store_id=store_id)
        return month_p
    if k == CardOrderKind.TIMES.value:
        return get_settings().MEMBER_CARD_TIMES_PRICE_YUAN
    raise HTTPException(status_code=400, detail="无效开卡类型")


def _is_pay_status_column_reject(exc: BaseException) -> bool:
    """MySQL ENUM 未扩展「已取消」等写入失败时识别。"""
    msg = str(exc).lower()
    if getattr(exc, "orig", None) is not None:
        msg = f"{msg} {str(exc.orig).lower()}"
    return any(
        token in msg
        for token in (
            "data truncated",
            "incorrect enum",
            "invalid enum",
            "1265",
            "check constraint",
            "check violation",
        )
    )


def is_member_card_order_cancelled(order: MemberCardOrder) -> bool:
    """是否已会员自助取消（含旧库 created_by 兼容标记）。"""
    if (order.pay_status or "").strip() == CardOrderPayStatus.CANCELLED.value:
        return True
    return (order.created_by or "").strip() == MINIPROGRAM_WECHAT_ORDER_CANCELLED_CREATOR


def _member_card_order_pay_status_display(order: MemberCardOrder) -> str:
    if is_member_card_order_cancelled(order):
        return CardOrderPayStatus.CANCELLED.value
    return (order.pay_status or "").strip()


def _persist_card_order_cancelled(db: Session, order: MemberCardOrder) -> None:
    """写入取消态；旧库 ENUM 仅 未缴/已缴 时回退 created_by 标记。"""
    order.pay_status = CardOrderPayStatus.CANCELLED.value
    try:
        with db.begin_nested():
            db.flush()
    except (DataError, IntegrityError, OperationalError, DBAPIError) as e:
        if not _is_pay_status_column_reject(e):
            raise
        order.pay_status = CardOrderPayStatus.UNPAID.value
        order.created_by = MINIPROGRAM_WECHAT_ORDER_CANCELLED_CREATOR
        base = (order.remark or "").strip()
        if _MEMBER_CARD_CANCEL_REMARK_TAG not in base:
            order.remark = (
                f"{base}\n{_MEMBER_CARD_CANCEL_REMARK_TAG}".strip()[:500]
                if base
                else _MEMBER_CARD_CANCEL_REMARK_TAG
            )
        db.flush()


def _pending_miniprogram_wechat_card_order_filters(*, member_id: int | None = None) -> list:
    """小程序微信自助开卡：未缴且未入账工单筛选条件。"""
    filters = [
        MemberCardOrder.pay_status == CardOrderPayStatus.UNPAID.value,
        MemberCardOrder.applied_to_member.is_(False),
        MemberCardOrder.pay_channel == CardPayChannel.WECHAT.value,
        MemberCardOrder.created_by == MINIPROGRAM_WECHAT_ORDER_CREATOR,
    ]
    if member_id is not None:
        filters.append(MemberCardOrder.member_id == int(member_id))
    return filters


def _unpaid_miniprogram_card_order_expire_cutoff():
    return beijing_now_naive() - timedelta(minutes=UNPAID_MINIPROGRAM_CARD_ORDER_EXPIRE_MINUTES)


def _find_pending_miniprogram_wechat_card_order(db: Session, member_id: int) -> MemberCardOrder | None:
    return db.scalars(
        select(MemberCardOrder)
        .where(*_pending_miniprogram_wechat_card_order_filters(member_id=member_id))
        .order_by(MemberCardOrder.id.desc())
        .limit(1)
    ).first()


def member_cancel_miniprogram_wechat_card_order(
    db: Session,
    *,
    member_id: int,
    order_id: int,
) -> str:
    """会员取消本人未支付的小程序微信开卡工单：释券、关微信单、标已取消。"""
    expire_stale_unpaid_miniprogram_card_orders(db, member_id=member_id)
    order = db.scalar(
        select(MemberCardOrder)
        .where(
            MemberCardOrder.id == int(order_id),
            MemberCardOrder.member_id == int(member_id),
        )
        .with_for_update()
    )
    if not order:
        raise HTTPException(status_code=404, detail="开卡订单不存在")
    if is_member_card_order_cancelled(order):
        return "订单已取消"
    ps = (order.pay_status or "").strip()
    if ps == CardOrderPayStatus.PAID.value:
        raise HTTPException(status_code=400, detail="订单已支付，无法取消")
    if ps == CardOrderPayStatus.REFUNDED.value:
        raise HTTPException(status_code=400, detail="订单已退款，无法取消")
    if ps != CardOrderPayStatus.UNPAID.value:
        raise HTTPException(status_code=400, detail="当前订单状态不可取消")
    if bool(order.applied_to_member):
        raise HTTPException(status_code=400, detail="订单已入账，无法取消")
    if (order.pay_channel or "").strip() != CardPayChannel.WECHAT.value:
        raise HTTPException(status_code=400, detail="仅小程序微信开卡订单可在此取消")
    if (order.created_by or "").strip() != MINIPROGRAM_WECHAT_ORDER_CREATOR:
        raise HTTPException(status_code=400, detail="当前订单不支持自助取消")

    if order.member_coupon_id is not None:
        release_member_coupon_for_order(
            db, order_biz=CouponLockedOrderBiz.MEMBER_CARD, order_id=int(order.id)
        )
        order.member_coupon_id = None
        order.original_amount_yuan = None
        order.coupon_discount_yuan = None
        _clear_coupon_from_card_order_remark(order)

    out_no = (order.out_trade_no or "").strip()
    if out_no:
        pay_cfg = get_merged_pay_config(db, int(order.tenant_id), store_id=int(order.store_id))
        _close_wechat_order_best_effort(out_no, pay=pay_cfg)

    _persist_card_order_cancelled(db, order)
    db.add(order)
    db.commit()
    db.refresh(order)
    return "订单已取消"


def expire_stale_unpaid_miniprogram_card_orders(db: Session, *, member_id: int | None = None) -> int:
    """购卡未支付超过阈值：释放 locked 券并恢复订单为原价（订单仍可继续支付）。"""
    cutoff = _unpaid_miniprogram_card_order_expire_cutoff()
    filters = _pending_miniprogram_wechat_card_order_filters(member_id=member_id)
    filters.append(MemberCardOrder.created_at < cutoff)
    stale = list(db.scalars(select(MemberCardOrder).where(*filters)).all())
    if not stale:
        return 0
    for order in stale:
        if order.member_coupon_id is not None:
            release_member_coupon_for_order(
                db, order_biz=CouponLockedOrderBiz.MEMBER_CARD, order_id=int(order.id)
            )
            orig = order.original_amount_yuan if order.original_amount_yuan is not None else order.amount_yuan
            order.amount_yuan = orig
            order.original_amount_yuan = None
            order.coupon_discount_yuan = None
            order.member_coupon_id = None
            _clear_coupon_from_card_order_remark(order)
            # 释券恢复原价后，微信侧仍可能是折后金额，须轮换商户单号
            pay_cfg = get_merged_pay_config(db, int(order.tenant_id), store_id=int(order.store_id))
            _rotate_member_card_order_out_trade_no(db, order, pay=pay_cfg, commit=False)
    db.commit()
    return len(stale)


def _card_order_checkout_original_amount(order: MemberCardOrder) -> Decimal:
    """结算用原价：有券时取 original_amount_yuan，否则取当前 amount_yuan。"""
    if order.original_amount_yuan is not None:
        return Decimal(order.original_amount_yuan).quantize(Decimal("0.01"))
    return Decimal(order.amount_yuan or 0).quantize(Decimal("0.01"))


def _member_card_coupon_checkout_context(order: MemberCardOrder) -> CouponCheckoutContext:
    return CouponCheckoutContext(
        checkout_biz=CouponLockedOrderBiz.MEMBER_CARD,
        original_amount_yuan=_card_order_checkout_original_amount(order),
        card_kind=order.card_kind,
        membership_template_id=int(order.membership_template_id) if order.membership_template_id else None,
    )


def apply_member_coupon_to_unpaid_card_order(
    db: Session,
    member_id: int,
    order_id: int,
    member_coupon_id: int | None,
) -> MemberCardOrder:
    """未支付购卡单：更换或移除优惠券（先释放旧锁再锁新券）。"""
    order = db.get(MemberCardOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="开卡订单不存在")
    if order.pay_status != CardOrderPayStatus.UNPAID.value:
        raise HTTPException(status_code=400, detail="仅未支付订单可使用优惠券")
    if order.applied_to_member:
        raise HTTPException(status_code=400, detail="订单状态不允许修改优惠券")
    if (order.pay_channel or "").strip() != CardPayChannel.WECHAT.value:
        raise HTTPException(status_code=400, detail="仅微信自助开卡单支持用券")
    if (order.created_by or "").strip() != "miniprogram":
        raise HTTPException(status_code=400, detail="仅小程序自助开卡单支持用券")

    release_member_coupon_for_order(
        db, order_biz=CouponLockedOrderBiz.MEMBER_CARD, order_id=int(order.id)
    )
    orig = _card_order_checkout_original_amount(order)
    old_payable = Decimal(order.amount_yuan or 0).quantize(Decimal("0.01"))

    if member_coupon_id is None:
        order.amount_yuan = orig
        order.original_amount_yuan = None
        order.coupon_discount_yuan = None
        order.member_coupon_id = None
        _clear_coupon_from_card_order_remark(order)
        new_payable = orig
    else:
        mem = db.get(Member, member_id)
        if not mem or mem.deleted_at is not None:
            raise HTTPException(status_code=404, detail="用户不存在")
        ctx = _member_card_coupon_checkout_context(order)
        o2, disc, payable = lock_member_coupon_for_order(
            db,
            member_coupon_id=int(member_coupon_id),
            member_id=int(member_id),
            store_id=int(mem.store_id),
            ctx=ctx,
            order_id=int(order.id),
        )
        order.original_amount_yuan = o2
        order.coupon_discount_yuan = disc
        order.amount_yuan = payable
        order.member_coupon_id = int(member_coupon_id)
        _apply_coupon_to_card_order_remark(
            db, order, member_coupon_id=int(member_coupon_id), discount_yuan=disc
        )
        new_payable = payable

    if new_payable.quantize(Decimal("0.01")) != old_payable:
        pay_cfg = get_merged_pay_config(db, int(order.tenant_id), store_id=int(order.store_id))
        _rotate_member_card_order_out_trade_no(db, order, pay=pay_cfg, commit=False)

    db.commit()
    db.refresh(order)
    return order


def _assert_no_pending_miniprogram_wechat_card_order(db: Session, member_id: int) -> None:
    """小程序微信开卡：已有未缴工单时不重复创建。"""
    pending = _find_pending_miniprogram_wechat_card_order(db, member_id)
    if pending is not None:
        raise HTTPException(
            status_code=409,
            detail=f"您有未支付的开卡订单（#{int(pending.id)}），请先完成支付后再下单",
        )


def create_miniprogram_member_card_order(
    db: Session,
    member_id: int,
    *,
    card_kind: str | None = None,
    delivery_start_date: date | None = None,
    membership_template_id: int | None = None,
    member_coupon_id: int | None = None,
) -> MemberCardOrder:
    expire_stale_unpaid_miniprogram_card_orders(db, member_id=member_id)
    pending = _find_pending_miniprogram_wechat_card_order(db, member_id)
    if pending is not None:
        if member_coupon_id is not None:
            return apply_member_coupon_to_unpaid_card_order(
                db, member_id, int(pending.id), int(member_coupon_id)
            )
        _assert_no_pending_miniprogram_wechat_card_order(db, member_id)
    m = db.get(Member, member_id)
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")

    is_renewal = _is_member_self_service_renewal(db, m)

    tpl: MembershipCardTemplate | None = None
    if membership_template_id is not None:
        tpl = get_membership_template_row(
            db,
            template_id=int(membership_template_id),
            tenant_id=int(m.tenant_id),
            store_id=int(m.store_id),
        )
        if not bool(tpl.is_active):
            raise HTTPException(status_code=400, detail="该卡包已下架")
        price = tpl.sale_price_yuan if tpl.sale_price_yuan is not None else tpl.list_price_yuan
        if price is None or Decimal(price) <= 0:
            raise HTTPException(status_code=400, detail="该卡包未设置有效售价")
        amt = Decimal(price).quantize(Decimal("0.01"))
        ck = enum_card_kind_for_template(tpl)
        # 老会员续卡：购卡时不校验/不改起送日，入账时沿用会员既有起送日
        d0 = None if is_renewal else delivery_start_date
        if d0 is not None and d0 < min_member_delivery_start_shanghai():
            raise HTTPException(
                status_code=400,
                detail="起送日期须不早于明日（上海业务日）",
            )
        rmk = _miniprogram_card_order_remark(
            f"卡包模版#{tpl.id}·{tpl.name.strip()}",
            is_renewal=is_renewal,
        )
        from app.services.meal_period.template_periods import meal_periods_from_template

        row = MemberCardOrder(
            member_id=member_id,
            tenant_id=int(m.tenant_id),
            store_id=int(m.store_id),
            membership_template_id=int(tpl.id),
            card_kind=ck,
            pay_channel=CardPayChannel.WECHAT.value,
            pay_status=CardOrderPayStatus.UNPAID.value,
            amount_yuan=amt,
            remark=rmk,
            delivery_start_date=d0,
            applied_to_member=False,
            meal_periods_snapshot=meal_periods_from_template(tpl),
            out_trade_no=_new_temp_out_trade_no(),
            wx_transaction_id=None,
            created_by="miniprogram",
        )
    else:
        k = (card_kind or "").strip()
        if k not in (CardOrderKind.WEEK.value, CardOrderKind.MONTH.value):
            raise HTTPException(status_code=400, detail="无效开卡类型")
        d0 = None if is_renewal else delivery_start_date
        if d0 is None and not is_renewal:
            raise HTTPException(status_code=400, detail="请选择起送日期")
        if d0 is not None and d0 < min_member_delivery_start_shanghai():
            raise HTTPException(
                status_code=400,
                detail="起送日期须不早于明日（上海业务日）",
            )
        amt = card_order_amount_yuan_for_kind(db, k, store_id=int(m.store_id))
        rmk = _miniprogram_card_order_remark(None, is_renewal=is_renewal)
        from app.services.meal_period.template_periods import classic_card_meal_periods_snapshot

        row = MemberCardOrder(
            member_id=member_id,
            tenant_id=int(m.tenant_id),
            store_id=int(m.store_id),
            membership_template_id=None,
            card_kind=k,
            pay_channel=CardPayChannel.WECHAT.value,
            pay_status=CardOrderPayStatus.UNPAID.value,
            amount_yuan=amt,
            remark=rmk,
            delivery_start_date=d0,
            applied_to_member=False,
            meal_periods_snapshot=classic_card_meal_periods_snapshot(),
            out_trade_no=_new_temp_out_trade_no(),
            wx_transaction_id=None,
            created_by="miniprogram",
        )
    db.add(row)
    db.flush()
    row.out_trade_no = _final_out_trade_no(int(row.id))

    if member_coupon_id is not None:
        ctx = CouponCheckoutContext(
            checkout_biz=CouponLockedOrderBiz.MEMBER_CARD,
            original_amount_yuan=amt,
            card_kind=row.card_kind,
            membership_template_id=int(row.membership_template_id) if row.membership_template_id else None,
        )
        orig, disc, payable = lock_member_coupon_for_order(
            db,
            member_coupon_id=int(member_coupon_id),
            member_id=int(member_id),
            store_id=int(m.store_id),
            ctx=ctx,
            order_id=int(row.id),
        )
        row.original_amount_yuan = orig
        row.coupon_discount_yuan = disc
        row.amount_yuan = payable
        row.member_coupon_id = int(member_coupon_id)
        _apply_coupon_to_card_order_remark(
            db, row, member_coupon_id=int(member_coupon_id), discount_yuan=disc
        )

    db.commit()
    db.refresh(row)
    return row


def prepare_wechat_jsapi_for_member_card_order(
    db: Session, member_id: int, order_id: int, client_ip: str
) -> dict[str, str]:
    expire_stale_unpaid_miniprogram_card_orders(db, member_id=member_id)
    order = db.get(MemberCardOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="开卡订单不存在")
    if order.pay_status == CardOrderPayStatus.PAID.value:
        raise HTTPException(status_code=400, detail="订单已支付")
    if order.pay_status == CardOrderPayStatus.REFUNDED.value:
        raise HTTPException(status_code=400, detail="订单已退款")
    if is_member_card_order_cancelled(order):
        raise HTTPException(status_code=400, detail="订单已取消")

    pay_cfg = get_merged_pay_config(db, int(order.tenant_id), store_id=int(order.store_id))
    perr = wechat_pay_misconfiguration_detail_merged(pay_cfg)
    if perr:
        raise HTTPException(status_code=503, detail=perr)

    member = db.get(Member, member_id)
    if not member or member.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    openid = (member.wx_mini_openid or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="请使用微信小程序授权登录后再支付")

    if order.amount_yuan is None:
        raise HTTPException(status_code=500, detail="订单金额异常")

    out_no = (order.out_trade_no or "").strip()
    if not out_no:
        raise HTTPException(status_code=500, detail="订单缺少商户单号")

    body_desc = _member_card_order_body_desc(db, order)
    _reconcile_wechat_out_trade_no_before_card_prepay(db, order, pay=pay_cfg)
    try:
        prepay_id = _unified_order_jsapi_for_member_card_order(
            db,
            order,
            body_desc=body_desc,
            openid=openid,
            client_ip=client_ip,
            pay=pay_cfg,
        )
    except WeChatPayV2Error as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    return build_miniprogram_pay_params(
        prepay_id, appid=pay_cfg.wx_mini_appid, api_key=pay_cfg.wechat_pay_api_key
    )


def sync_member_card_order_from_wechat_query(
    db: Session, member_id: int, order_id: int
) -> tuple[bool, str]:
    """
    支付成功后由小程序主动拉单：调微信 orderquery，若已支付则与异步通知同路径入账（幂等）。

    解决异步通知 URL 不可达、白名单/漏配等导致「钱已付但库未更」问题。
    """
    order = db.get(MemberCardOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        return False, "order_not_found"
    ch = (order.pay_channel or "").strip()
    if ch == "线下":
        return False, "not_wechat_order"
    cb = (order.created_by or "").strip()
    if cb == "miniprogram-offline":
        return False, "not_wechat_order"

    out_no = (order.out_trade_no or "").strip()
    if not out_no:
        return False, "missing_out_trade_no"

    if order.pay_status == CardOrderPayStatus.REFUNDED.value:
        return False, "order_refunded"

    if order.applied_to_member and order.pay_status == CardOrderPayStatus.PAID.value:
        return True, "already_synced"

    try:
        pay_cfg = get_merged_pay_config(db, int(order.tenant_id), store_id=int(order.store_id))
        data = query_order_by_out_trade_no(out_no, pay=pay_cfg)
    except WeChatPayV2Error as e:
        return False, f"wechat_query:{str(e)}"[:220]

    if (data.get("result_code") or "").upper() != "SUCCESS":
        err_c = (data.get("err_code") or "").strip().upper()
        if err_c == "ORDERNOTEXIST":
            return False, "wechat_order_not_found"
        err_msg = (data.get("err_code_des") or data.get("err_code") or "query_fail")[:200]
        return False, err_msg

    ts = (data.get("trade_state") or "").strip().upper()
    if ts in ("", "NOTPAY"):
        return False, "not_paid"
    if ts == "USERPAYING":
        return False, "PAY_USERPAYING"
    if ts != "SUCCESS":
        return False, f"trade_state_{ts}"

    out_p = (data.get("out_trade_no") or "").strip() or out_no
    tx_id = (data.get("transaction_id") or "").strip()
    try:
        total_fee = int((data.get("total_fee") or "0").strip() or 0)
    except ValueError:
        return False, "invalid_total_fee"
    if not out_p:
        return False, "missing_out_in_response"
    parsed = WechatPayNotifyParsed(
        out_trade_no=out_p,
        transaction_id=tx_id,
        total_fee=total_fee,
    )
    ok, reason = finalize_member_card_order_wechat_pay(db, parsed)
    if ok:
        return True, reason
    return False, reason


def sync_member_card_from_wechat_or_raise(db: Session, member_id: int, order_id: int) -> None:
    """
    供 HTTP 层调用：拉单成功则已 `commit` 入账；失败时抛出与会员端接口一致的 `HTTPException`。
    """
    from fastapi import HTTPException

    ok, reason = sync_member_card_order_from_wechat_query(db, member_id, order_id)
    if not ok:
        if reason == "PAY_USERPAYING":
            raise HTTPException(
                status_code=400,
                detail="微信侧支付处理中，请稍候再试或下拉刷新「我的」",
            )
        if reason == "order_not_found":
            raise HTTPException(status_code=404, detail="开卡订单不存在")
        if reason == "not_wechat_order":
            raise HTTPException(status_code=400, detail="该工单非微信自助支付，无需此同步")
        if reason == "order_refunded":
            raise HTTPException(status_code=400, detail="订单已退款")
        if reason.startswith("wechat_query:"):
            raise HTTPException(
                status_code=502, detail=reason.replace("wechat_query:", "", 1)[:200]
            )
        raise HTTPException(status_code=400, detail=reason[:200])


def sync_member_card_from_wechat_admin_or_raise(
    db: Session, order_id: int, *, store_id: int | None = None
) -> None:
    """管理端：按工单 id 向微信查单并记已缴（补救「已扣款但库未更」）。"""
    from fastapi import HTTPException

    order = db.get(MemberCardOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    if store_id is not None and int(order.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="工单不存在")
    sync_member_card_from_wechat_or_raise(db, int(order.member_id), int(order_id))


def _is_miniprogram_self_service_card_order(order: MemberCardOrder) -> bool:
    """小程序用户自助开卡/续卡（含卡包模版）；支付后次数即时入账，客服通知用于核对配送信息。"""
    return (order.created_by or "").strip() == "miniprogram"


def _card_kind_label_for_miniprogram_notification(db: Session, order: MemberCardOrder) -> str:
    """系统消息卡型：优先展示卡包模版名称，避免全餐卡仅显示「周卡」误导核对。"""
    tpl_id = getattr(order, "membership_template_id", None)
    if tpl_id is not None:
        tpl = db.get(MembershipCardTemplate, int(tpl_id))
        if tpl is not None:
            name = (tpl.name or "").strip()
            kind = (tpl.kind_label or "").strip()
            if name and kind:
                return f"{name}（{kind}）"
            if name:
                return name
            if kind:
                return kind
    return (order.card_kind or "").strip() or "会员卡"


def _notify_miniprogram_card_order_pending_cs_review(db: Session, order: MemberCardOrder) -> None:
    member = db.get(Member, int(order.member_id))
    create_miniprogram_card_order_pending_notification(
        db,
        store_id=int(order.store_id),
        order_id=int(order.id),
        card_kind=_card_kind_label_for_miniprogram_notification(db, order),
        member_id=int(order.member_id),
        member_phone=(member.phone if member else None),
        member_name=(member.name if member else None),
        delivery_start_date=order.delivery_start_date,
    )


def finalize_member_card_order_wechat_pay(db: Session, parsed: WechatPayNotifyParsed) -> tuple[bool, str]:
    order = db.scalar(
        select(MemberCardOrder)
        .where(MemberCardOrder.out_trade_no == parsed.out_trade_no)
        .with_for_update()
    )
    if not order:
        return False, "order_not_found"

    if order.pay_status == CardOrderPayStatus.REFUNDED.value:
        return False, "order_refunded"

    if order.pay_status == CardOrderPayStatus.PAID.value:
        apply_paid_card_order_to_member_if_pending(db, order, operator="wechat_notify")
        mark_member_coupon_used_for_order(
            db, order_biz=CouponLockedOrderBiz.MEMBER_CARD, order_id=int(order.id)
        )
        db.commit()
        return True, "already_paid"

    if order.amount_yuan is None:
        return False, "amount_missing"

    expect_fen = yuan_decimal_to_fen(order.amount_yuan)
    if parsed.total_fee != expect_fen:
        logger.error(
            "微信回调金额不一致(开卡) out=%s expect_fen=%s got_fen=%s",
            parsed.out_trade_no,
            expect_fen,
            parsed.total_fee,
        )
        return False, "amount_mismatch"

    order.pay_status = CardOrderPayStatus.PAID.value
    order.pay_channel = CardPayChannel.WECHAT.value
    tid = (parsed.transaction_id or "").strip()
    order.wx_transaction_id = tid or order.wx_transaction_id
    # 支付成功即写入会员次数；无起送日时不激活，待用户完善配送后再派单
    apply_paid_card_order_to_member_if_pending(db, order, operator="wechat_notify")
    if _is_miniprogram_self_service_card_order(order):
        oid = int(order.id)
        mid = int(order.member_id)
        out_sn = parsed.out_trade_no
        try:
            with db.begin_nested():
                _notify_miniprogram_card_order_pending_cs_review(db, order)
        except Exception:
            # 待核对配送通知失败不应回滚「已缴/已入账」
            logger.exception(
                "小程序购卡待核对配送通知写入失败 order_id=%s member_id=%s out=%s",
                oid,
                mid,
                out_sn,
            )
    mark_member_coupon_used_for_order(
        db, order_biz=CouponLockedOrderBiz.MEMBER_CARD, order_id=int(order.id)
    )
    db.commit()
    logger.info(
        "开卡工单微信入账成功 order_id=%s member_id=%s out=%s delivery_start=%s",
        int(order.id),
        int(order.member_id),
        parsed.out_trade_no,
        order.delivery_start_date.isoformat() if order.delivery_start_date else None,
    )
    return True, "paid"


def member_card_order_user_dict(order: MemberCardOrder) -> dict:
    return {
        "id": int(order.id),
        "card_kind": order.card_kind,
        "amount_yuan": _format_amount_yuan(order.amount_yuan) if order.amount_yuan is not None else None,
        "original_amount_yuan": (
            _format_amount_yuan(order.original_amount_yuan) if order.original_amount_yuan is not None else None
        ),
        "coupon_discount_yuan": (
            _format_amount_yuan(order.coupon_discount_yuan) if order.coupon_discount_yuan is not None else None
        ),
        "member_coupon_id": int(order.member_coupon_id) if order.member_coupon_id is not None else None,
        "pay_status": _member_card_order_pay_status_display(order),
        "delivery_start_date": order.delivery_start_date.isoformat() if order.delivery_start_date else None,
        "out_trade_no": (order.out_trade_no or "").strip() or None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "remark": ((order.remark or "").strip() or None),
    }


def get_member_card_order_for_user(db: Session, member_id: int, order_id: int) -> dict:
    """小程序：单条开卡/续卡工单详情（仅本人）。"""
    order = db.get(MemberCardOrder, int(order_id))
    if not order or int(order.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="开卡订单不存在")
    return member_card_order_user_dict(order)


def list_member_card_orders_for_user(
    db: Session,
    member_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    list_status: str | None = None,
) -> tuple[list[dict], int]:
    """小程序「商城订单」：会员工单（周/月/次卡、卡包）列表。"""
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    filters = [MemberCardOrder.member_id == int(member_id)]
    ls = (list_status or "all").strip().lower()
    if ls == "pending_pay":
        filters.append(MemberCardOrder.pay_status == CardOrderPayStatus.UNPAID.value)
        filters.append(MemberCardOrder.created_by == MINIPROGRAM_WECHAT_ORDER_CREATOR)
    elif ls == "completed":
        filters.append(MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value)
    elif ls != "all":
        ls = "all"

    total = int(
        db.scalar(select(func.count()).select_from(MemberCardOrder).where(*filters)) or 0
    )
    rows = db.scalars(
        select(MemberCardOrder)
        .where(*filters)
        .order_by(MemberCardOrder.created_at.desc(), MemberCardOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [member_card_order_user_dict(r) for r in rows], total


def _sync_member_card_order_refunded_local(db: Session, order: MemberCardOrder) -> str:
    """
    将本地工单标记为「已退款」（幂等）。

    微信退款 API 已成功但本地 commit 失败时，重试入口发现 trade_state=REFUND 可据此对齐状态。
    """
    out_refund_no = f"RFMC{order.id}"[:32]
    if order.pay_status == CardOrderPayStatus.REFUNDED.value:
        return out_refund_no
    order.pay_status = CardOrderPayStatus.REFUNDED.value
    db.add(order)
    db.commit()
    return out_refund_no


def admin_wechat_refund_member_card_order(
    db: Session, *, order_id: int, store_id: int, require_mall_template: bool
) -> dict[str, str]:
    """管理端：微信已缴会员卡工单全额原路退款（须配置商户 API 证书）。"""
    order = db.get(MemberCardOrder, int(order_id))
    if not order or int(order.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    if require_mall_template and order.membership_template_id is None:
        raise ValueError("该入口仅适用于商城卡包订单（绑定会员卡模版）")
    if order.pay_status != CardOrderPayStatus.PAID.value:
        raise ValueError('仅「已缴」订单可发起微信退款')
    if (order.pay_channel or "").strip() != CardPayChannel.WECHAT.value:
        raise ValueError("仅微信支付订单可原路退回")
    if order.pay_status == CardOrderPayStatus.REFUNDED.value:
        raise ValueError("订单已退款")
    revoke_paid_card_order_member_sync(
        db, order, operator="admin:mall_card_wechat_refund"
    )
    out_no = (order.out_trade_no or "").strip()
    if not out_no:
        raise ValueError("订单缺少商户单号，无法退款")

    pay_cfg = get_merged_pay_config(db, int(order.tenant_id), store_id=int(order.store_id))
    q = query_order_by_out_trade_no(out_no, pay=pay_cfg)
    trade_state = (q.get("trade_state") or "").strip().upper()
    # 微信已退款但本地仍为「已缴」：首次退款 API 成功而 commit 失败时的补救（幂等）
    if trade_state == "REFUND":
        out_refund_no = _sync_member_card_order_refunded_local(db, order)
        return {
            "message": "微信侧已完成退款，本地订单状态已同步为「已退款」",
            "out_refund_no": out_refund_no,
        }
    if trade_state != "SUCCESS":
        raise ValueError(
            f"微信侧订单状态为「{trade_state or '未知'}」，需为支付成功（SUCCESS）才可退款",
        )
    try:
        total_fee = int((q.get("total_fee") or "0").strip())
    except ValueError as e:
        raise ValueError("无法解析微信订单金额") from e
    out_refund_no = f"RFMC{order.id}"[:32]
    refund_order_v2(
        out_trade_no=out_no,
        out_refund_no=out_refund_no,
        total_fee_fen=total_fee,
        refund_fee_fen=total_fee,
        pay=pay_cfg,
        transaction_id=(order.wx_transaction_id or "").strip() or None,
    )
    order.pay_status = CardOrderPayStatus.REFUNDED.value
    db.add(order)
    db.commit()
    return {"message": "微信退款已受理，资金将按支付渠道原路退回用户", "out_refund_no": out_refund_no}
