"""微信支付 v2 异步通知（无 JWT）。"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.wechat_pay_v2 import (
    notify_client_ip_allowed,
    resolve_request_client_ip,
    xml_to_dict,
)
from app.services.wechat_pay_notify_dispatch import apply_wechat_pay_notify

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
async def wechat_pay_notify(request: Request, db: Session = Depends(get_db)):
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
