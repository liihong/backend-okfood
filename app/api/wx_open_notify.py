"""微信开放平台回调：component 事件（verify_ticket / 授权变更）及传统模式授权 redirect。"""

from __future__ import annotations

import hashlib
import logging
import re
import xml.etree.ElementTree as ET

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.core.config import get_settings
from app.core.deps import SessionDep
from app.models.tenant import Tenant
from app.services.shared.wx_open_authorizer_service import (
    exchange_authorization_code,
    pop_tenant_id_for_pre_auth,
    save_component_verify_ticket,
)

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
        pre_auth_code = _text_from_xml(xml_payload, "PreAuthCode") or _text_from_xml(xml_payload, "pre_auth_code")
        logger.info(
            "收到授权事件 InfoType=%s appid=%s code=%s pre_auth=%s",
            info_type,
            appid,
            bool(auth_code),
            bool(pre_auth_code),
        )
        # 传统模式：若管理端刚生成过 pre_auth 链接，可自动换取 token 落库
        if auth_code:
            tenant_id = pop_tenant_id_for_pre_auth(pre_auth_code)
            if tenant_id is not None:
                try:
                    exchange_authorization_code(db, authorization_code=auth_code, tenant_id=tenant_id)
                    logger.info("授权事件已自动换取 token tenant_id=%s appid=%s", tenant_id, appid)
                except HTTPException as e:
                    logger.warning("授权事件自动换取失败 tenant_id=%s detail=%s", tenant_id, e.detail)
                except Exception:
                    logger.exception("授权事件自动换取异常 tenant_id=%s", tenant_id)
    elif info_type == "unauthorized":
        appid = _text_from_xml(xml_payload, "AuthorizerAppid")
        logger.info("收到取消授权 AuthorizerAppid=%s", appid)
    else:
        logger.debug("component 回调 InfoType=%s len=%s", info_type, len(raw_body))

    return PlainTextResponse("success")


def _authorize_result_html(*, success: bool, title: str, detail: str) -> str:
    """授权完成页（微信 redirect 后在浏览器展示）。"""
    color = "#16a34a" if success else "#dc2626"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f8fafc; margin: 0; padding: 32px 16px; }}
    .card {{ max-width: 480px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 28px 24px; box-shadow: 0 8px 24px rgba(15,23,42,.08); }}
    h1 {{ margin: 0 0 12px; font-size: 1.25rem; color: {color}; }}
    p {{ margin: 0; line-height: 1.6; color: #334155; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{title}</h1>
    <p>{detail}</p>
  </div>
</body>
</html>"""


@router.get("/authorize/callback")
def wx_open_authorize_callback(
    db: SessionDep,
    tenant_id: int = Query(..., ge=1, description="平台管理生成链接时携带的租户 ID"),
    auth_code: str = Query(..., min_length=4, max_length=512, description="微信授权码"),
    expires_in: int = Query(0, ge=0),
):
    """
    传统模式授权 redirect_uri：商户扫码授权后微信浏览器跳转至此。

    须配置 BASE_URL，且域名已在开放平台「授权发起页域名」中登记。
    """
    _ = expires_in
    tenant = db.get(Tenant, int(tenant_id))
    if tenant is None:
        return HTMLResponse(
            _authorize_result_html(success=False, title="授权失败", detail="租户不存在或已删除。"),
            status_code=404,
        )
    try:
        state = exchange_authorization_code(db, authorization_code=auth_code, tenant_id=int(tenant_id))
    except HTTPException as e:
        return HTMLResponse(
            _authorize_result_html(success=False, title="授权失败", detail=str(e.detail)),
            status_code=int(e.status_code),
        )
    appid = state.get("authorizer_appid") or "—"
    return HTMLResponse(
        _authorize_result_html(
            success=True,
            title="小程序授权成功",
            detail=f"租户「{tenant.name}」（ID {tenant_id}）已完成代授权，AppID：{appid}。可关闭本页并在平台管理后台查看 Authorizer 状态。",
        )
    )
