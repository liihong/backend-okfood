"""小程序自助开卡/续卡：创建工单、微信 JSAPI 预下单、支付回调入账。"""

from __future__ import annotations

import logging
import secrets
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import min_member_delivery_start_shanghai
from app.integrations.wechat_pay_v2 import (
    WeChatPayV2Error,
    WechatPayNotifyParsed,
    build_miniprogram_pay_params,
    query_order_by_out_trade_no,
    unified_order_jsapi,
    wechat_pay_misconfiguration_detail,
    yuan_decimal_to_fen,
)
from app.models.enums import CardOrderKind, CardOrderPayStatus, CardPayChannel
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.services.member_card_order_service import apply_paid_card_order_to_member_if_pending
from app.services.store_config_service import get_member_card_prices_yuan

logger = logging.getLogger(__name__)


def _new_temp_out_trade_no() -> str:
    return f"T{secrets.token_hex(14)}"[:32]


def _final_out_trade_no(order_id: int) -> str:
    s = f"OKC{order_id}"
    if len(s) > 32:
        raise HTTPException(status_code=500, detail="开卡订单号超长")
    return s


def _format_amount_yuan(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01')):.2f}"


def card_order_amount_yuan_for_kind(db: Session, card_kind: str) -> Decimal:
    week_p, month_p = get_member_card_prices_yuan(db)
    k = (card_kind or "").strip()
    if k == CardOrderKind.WEEK.value:
        return week_p
    if k == CardOrderKind.MONTH.value:
        return month_p
    raise HTTPException(status_code=400, detail="无效开卡类型")


def create_miniprogram_member_card_order(
    db: Session,
    member_id: int,
    *,
    card_kind: str,
    delivery_start_date: date,
) -> MemberCardOrder:
    k = (card_kind or "").strip()
    if k not in (CardOrderKind.WEEK.value, CardOrderKind.MONTH.value):
        raise HTTPException(status_code=400, detail="无效开卡类型")
    if delivery_start_date < min_member_delivery_start_shanghai():
        raise HTTPException(
            status_code=400,
            detail="起送日期须不早于允许的最小业务日（上海；当日 10:00 前最早今天，10:00 及之后最早明天）",
        )

    m = db.get(Member, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="用户不存在")

    amt = card_order_amount_yuan_for_kind(db, k)
    row = MemberCardOrder(
        member_id=member_id,
        card_kind=k,
        pay_channel=CardPayChannel.WECHAT.value,
        pay_status=CardOrderPayStatus.UNPAID.value,
        amount_yuan=amt,
        remark=None,
        delivery_start_date=delivery_start_date,
        applied_to_member=False,
        out_trade_no=_new_temp_out_trade_no(),
        wx_transaction_id=None,
        created_by="miniprogram",
    )
    db.add(row)
    db.flush()
    row.out_trade_no = _final_out_trade_no(int(row.id))
    db.commit()
    db.refresh(row)
    return row


def prepare_wechat_jsapi_for_member_card_order(
    db: Session, member_id: int, order_id: int, client_ip: str
) -> dict[str, str]:
    pay_cfg = wechat_pay_misconfiguration_detail()
    if pay_cfg:
        raise HTTPException(status_code=503, detail=pay_cfg)

    order = db.get(MemberCardOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="开卡订单不存在")
    if order.pay_status == CardOrderPayStatus.PAID.value:
        raise HTTPException(status_code=400, detail="订单已支付")

    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="用户不存在")
    openid = (member.wx_mini_openid or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="请使用微信小程序授权登录后再支付")

    if order.amount_yuan is None:
        raise HTTPException(status_code=500, detail="订单金额异常")

    out_no = (order.out_trade_no or "").strip()
    if not out_no:
        raise HTTPException(status_code=500, detail="订单缺少商户单号")

    kind_label = (order.card_kind or "").strip() or "套卡"
    body_desc = f"会员{kind_label}开卡"
    try:
        prepay_id = unified_order_jsapi(
            out_trade_no=out_no,
            body=body_desc,
            total_fee_fen=yuan_decimal_to_fen(order.amount_yuan),
            openid=openid,
            spbill_create_ip=client_ip,
        )
    except WeChatPayV2Error as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    return build_miniprogram_pay_params(prepay_id)


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

    if order.applied_to_member and order.pay_status == CardOrderPayStatus.PAID.value:
        return True, "already_synced"

    try:
        data = query_order_by_out_trade_no(out_no)
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
        if reason.startswith("wechat_query:"):
            raise HTTPException(
                status_code=502, detail=reason.replace("wechat_query:", "", 1)[:200]
            )
        raise HTTPException(status_code=400, detail=reason[:200])


def finalize_member_card_order_wechat_pay(db: Session, parsed: WechatPayNotifyParsed) -> tuple[bool, str]:
    order = db.scalar(
        select(MemberCardOrder)
        .where(MemberCardOrder.out_trade_no == parsed.out_trade_no)
        .with_for_update()
    )
    if not order:
        return False, "order_not_found"

    if order.pay_status == CardOrderPayStatus.PAID.value:
        apply_paid_card_order_to_member_if_pending(db, order, operator="wechat_notify")
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
    apply_paid_card_order_to_member_if_pending(db, order, operator="wechat_notify")
    db.commit()
    return True, "paid"


def member_card_order_user_dict(order: MemberCardOrder) -> dict:
    return {
        "id": int(order.id),
        "card_kind": order.card_kind,
        "amount_yuan": _format_amount_yuan(order.amount_yuan) if order.amount_yuan is not None else None,
        "pay_status": order.pay_status,
        "delivery_start_date": order.delivery_start_date.isoformat() if order.delivery_start_date else None,
        "out_trade_no": (order.out_trade_no or "").strip() or None,
    }
