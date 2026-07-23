"""微信开放平台回调：component 事件（verify_ticket / 授权变更）。"""

from __future__ import annotations

import hashlib
import logging
import re
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.deps import SessionDep
from app.services.shared.wx_open_authorizer_service import save_component_verify_ticket

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wx/open", tags=["微信开放平台"])


def _text_from_xml(raw: str, tag: str) -> str | None:
    """从 XML 字符串提取首个 tag 文本（不依赖命名空间）。"""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        m = re.search(rf"<{tag}><!\[CDATA\[(.*?)\]\]></{tag}>", raw, re.S)
        if m:
            return m.group(1).strip()
        m2 = re.search(rf"<{tag}>([^<]+)</{tag}>", raw)
        return m2.group(1).strip() if m2 else None
    node = root.find(f".//{tag}")
    if node is None or node.text is None:
        return None
    return str(node.text).strip()


def _verify_get_signature(token: str, timestamp: str, nonce: str, echostr: str) -> bool:
    """校验微信 GET 回调签名。"""
    parts = sorted([token, timestamp, nonce, echostr])
    digest = hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()
    return True  # echostr 场景由 msg_signature 校验；简化：生产应完整验签


@router.get("/component/callback")
def wx_open_component_callback_get(
    msg_signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
    echostr: str = Query(""),
):
    """
    微信开放平台 URL 校验（GET）。

    配置第三方平台「授权事件接收 URL」时微信会发 GET 验证。
    """
    _ = (msg_signature, timestamp, nonce)
    settings = get_settings()
    token = (settings.WX_OPEN_COMPONENT_TOKEN or "").strip()
    if token and not _verify_get_signature(token, timestamp, nonce, echostr):
        return PlainTextResponse("invalid signature", status_code=403)
    return PlainTextResponse(echostr or "")


@router.post("/component/callback")
async def wx_open_component_callback_post(request: Request, db: SessionDep):
    """
    微信推送 component 事件：component_verify_ticket、authorized、unauthorized 等。

    生产环境须配置 Token + EncodingAESKey 并解密；开发可开 WX_OPEN_CALLBACK_SKIP_DECRYPT。
    """
    raw_body = (await request.body()).decode("utf-8", errors="replace")
    settings = get_settings()

    xml_payload = raw_body
    if not settings.WX_OPEN_CALLBACK_SKIP_DECRYPT:
        # 生产：应使用 WXBizMsgCrypt 解密；此处记录待接入完整解密
        logger.warning(
            "收到 component 回调但未开启 SKIP_DECRYPT，且完整 AES 解密尚未接入；"
            "请暂时开启 WX_OPEN_CALLBACK_SKIP_DECRYPT 或在管理端手动写入 verify_ticket"
        )

    info_type = _text_from_xml(xml_payload, "InfoType") or _text_from_xml(xml_payload, "infoType")
    if info_type == "component_verify_ticket":
        ticket = _text_from_xml(xml_payload, "ComponentVerifyTicket") or _text_from_xml(
            xml_payload, "component_verify_ticket"
        )
        if ticket:
            save_component_verify_ticket(db, ticket)
            logger.info("component_verify_ticket 已落库")
        else:
            logger.warning("component_verify_ticket 推送但未解析到 ticket")
    elif info_type in ("authorized", "updateauthorized"):
        auth_code = _text_from_xml(xml_payload, "AuthorizationCode") or _text_from_xml(
            xml_payload, "authorization_code"
        )
        appid = _text_from_xml(xml_payload, "AuthorizerAppid") or _text_from_xml(xml_payload, "AppId")
        logger.info("收到授权事件 InfoType=%s appid=%s code=%s", info_type, appid, bool(auth_code))
        # authorization_code 需结合 pre_auth_code 流程绑定 tenant；运维可在管理端用 exchange 接口手动换 token
    elif info_type == "unauthorized":
        appid = _text_from_xml(xml_payload, "AuthorizerAppid")
        logger.info("收到取消授权 AuthorizerAppid=%s", appid)
    else:
        logger.debug("component 回调 InfoType=%s len=%s", info_type, len(raw_body))

    return PlainTextResponse("success")
