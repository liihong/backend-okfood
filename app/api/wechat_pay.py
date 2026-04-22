"""微信支付 v2 异步通知（无 JWT）。"""

import logging

from fastapi import APIRouter, Depends, Request, Response

from app.core.deps import SessionDep, member_subject
from app.core.limiter import limiter
from app.integrations.wechat_pay_v2 import (
    notify_client_ip_allowed,
    resolve_request_client_ip,
    xml_to_dict,
)
from app.services.member_card_pay_service import sync_member_card_from_wechat_or_raise
from app.services.member_service import get_member
from app.services.wechat_pay_notify_dispatch import apply_wechat_pay_notify
from app.utils.response import dump_model, success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pay/wechat", tags=["微信支付"])


def _notify_xml(success: bool, msg: str = "OK") -> Response:
    code = "SUCCESS" if success else "FAIL"
    safe = (msg or "")[:200]
    body = (
        f"<xml><return_code><![CDATA[{code}]]></return_code>"
        f"<return_msg><![CDATA[{safe}]]></return_msg></xml>"
    )
    return Response(content=body.encode("utf-8"), media_type="application/xml; charset=utf-8")


@router.post("/notify")
async def wechat_pay_notify(request: Request, db: SessionDep):
    raw_bytes = await request.body()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        logger.warning("微信回调非 UTF-8 正文")
        return _notify_xml(False, "charset")

    fwd = request.headers.get("x-forwarded-for")
    ip = resolve_request_client_ip(fwd, request.client.host if request.client else None)
    if not notify_client_ip_allowed(ip):
        logger.warning("微信回调 IP 被拒绝: %s", ip)
        return _notify_xml(False, "ip")

    try:
        data = xml_to_dict(text)
    except Exception as e:
        logger.warning("微信回调 XML 解析失败: %s", e)
        return _notify_xml(False, "xml")

    try:
        ok, reason = apply_wechat_pay_notify(db, data)
    except Exception:
        logger.exception("微信回调处理异常")
        db.rollback()
        return _notify_xml(False, "internal")

    if not ok:
        logger.warning("微信回调业务未受理: %s data=%s", reason, {k: data.get(k) for k in ("out_trade_no", "total_fee")})
        return _notify_xml(False, reason)
    return _notify_xml(True, "OK")


@router.post("/member-card-order-sync/{order_id}")
@limiter.limit("30/minute")
def wechat_member_card_order_sync_after_pay(
    request: Request,
    order_id: int,
    db: SessionDep,
    member_id: int = Depends(member_subject),
):
    """
    与 `POST /api/user/member-card-orders/{order_id}/sync-wechat-pay` 等价（需会员 JWT）。

    支付成功拉单入账；若仍见 404，请确认已部署最新代码并重启服务，或检查是否误用 GET。
    """
    _ = request
    sync_member_card_from_wechat_or_raise(db, member_id, order_id)
    member = get_member(db, member_id)
    return success(data=dump_model(member), msg="支付结果已同步")
