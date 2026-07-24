"""微信开放平台 · authorizer token 落库、刷新与登录辅助。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import beijing_now_naive
from app.integrations.wechat_mini import WeChatMiniError
from app.models.tenant_integration_settings import TenantIntegrationSettings
from app.models.wx_open_component_state import WxOpenComponentState
from app.services.shared.tenant_integration_service import get_tenant_integration_row

logger = logging.getLogger(__name__)

AUTHORIZER_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/component/api_authorizer_token"
QUERY_AUTH_URL = "https://api.weixin.qq.com/cgi-bin/component/api_query_auth"
CREATE_PREAUTH_URL = "https://api.weixin.qq.com/cgi-bin/component/api_create_preauthcode"
COMPONENT_LOGIN_PAGE_URL = "https://mp.weixin.qq.com/cgi-bin/componentloginpage"

# 传统模式：pre_auth_code -> (tenant_id, expires_at_unix)；进程内缓存，重启后需重新生成链接
_pending_pre_auth_tenant: dict[str, tuple[int, float]] = {}


def _s(raw: str | None) -> str:
    return (raw or "").strip()


def _ensure_component_state_row(db: Session) -> WxOpenComponentState:
    row = db.get(WxOpenComponentState, 1)
    if row is None:
        row = WxOpenComponentState(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def save_component_verify_ticket(db: Session, ticket: str) -> None:
    """保存微信推送的 component_verify_ticket。"""
    t = _s(ticket)
    if not t:
        return
    row = _ensure_component_state_row(db)
    row.verify_ticket = t
    row.ticket_updated_at = beijing_now_naive()
    db.commit()


def get_component_verify_ticket(db: Session) -> str:
    row = db.get(WxOpenComponentState, 1)
    return _s(row.verify_ticket if row else None)


@dataclass(frozen=True)
class AuthorizerTokenState:
    tenant_id: int
    authorizer_appid: str
    has_access_token: bool
    has_refresh_token: bool
    token_expires_at: str | None
    authorized_at: str | None
    authorizer_mode_active: bool
    component_ticket_present: bool


def tenant_has_authorizer_tokens(db: Session, tenant_id: int) -> bool:
    """租户是否已落库 authorizer refresh_token（可走第三方平台登录）。"""
    row = get_tenant_integration_row(db, int(tenant_id))
    return bool(row and _s(row.wx_authorizer_refresh_token))


def get_authorizer_admin_state(db: Session, tenant_id: int) -> dict[str, Any]:
    """管理端：authorizer 状态摘要（不回显 token 明文）。"""
    row = get_tenant_integration_row(db, int(tenant_id))
    appid = _s(row.wx_mini_appid if row else None)
    ticket = get_component_verify_ticket(db)
    settings = get_settings()
    return {
        "tenant_id": int(tenant_id),
        "authorizer_appid": appid or None,
        "has_authorizer_access_token": bool(row and _s(row.wx_authorizer_access_token)),
        "has_authorizer_refresh_token": bool(row and _s(row.wx_authorizer_refresh_token)),
        "token_expires_at": (
            row.wx_authorizer_token_expires_at.isoformat()
            if row and row.wx_authorizer_token_expires_at
            else None
        ),
        "authorized_at": (
            row.wx_authorizer_authorized_at.isoformat() if row and row.wx_authorizer_authorized_at else None
        ),
        "authorizer_mode_active": tenant_has_authorizer_tokens(db, int(tenant_id)),
        "component_platform_configured": bool(
            _s(settings.WX_OPEN_COMPONENT_APPID) and _s(settings.WX_OPEN_COMPONENT_SECRET)
        ),
        "component_ticket_present": bool(ticket),
    }


def _integration_row_or_create(db: Session, tenant_id: int) -> TenantIntegrationSettings:
    row = get_tenant_integration_row(db, int(tenant_id))
    if row is None:
        row = TenantIntegrationSettings(tenant_id=int(tenant_id))
        db.add(row)
        db.flush()
    return row


def patch_authorizer_tokens_admin(
    db: Session,
    tenant_id: int,
    *,
    authorizer_refresh_token: str | None = None,
    authorizer_access_token: str | None = None,
    clear: bool = False,
) -> dict[str, Any]:
    """平台管理：手动写入或清除 authorizer token（授权回调未接通时的运维入口）。"""
    row = _integration_row_or_create(db, int(tenant_id))
    if clear:
        row.wx_authorizer_access_token = None
        row.wx_authorizer_refresh_token = None
        row.wx_authorizer_token_expires_at = None
        row.wx_authorizer_authorized_at = None
        db.commit()
        return get_authorizer_admin_state(db, int(tenant_id))

    if authorizer_refresh_token is not None:
        rt = _s(authorizer_refresh_token)
        row.wx_authorizer_refresh_token = rt or None
    if authorizer_access_token is not None:
        at = _s(authorizer_access_token)
        row.wx_authorizer_access_token = at or None
        if at:
            row.wx_authorizer_token_expires_at = beijing_now_naive() + timedelta(hours=2)
            row.wx_authorizer_authorized_at = beijing_now_naive()
    db.commit()
    return get_authorizer_admin_state(db, int(tenant_id))


def _public_api_base_or_raise() -> str:
    """生成授权回调 redirect_uri 所需的对外 API 根地址。"""
    base = get_settings().public_base_for_assets
    if not base:
        raise HTTPException(
            status_code=503,
            detail="请先在 .env 配置 BASE_URL（对外 HTTPS 根地址），用于传统模式授权回调",
        )
    return base


def build_tenant_authorize_redirect_uri(tenant_id: int) -> str:
    """传统模式授权完成后的 redirect_uri（须与开放平台「授权发起页域名」一致）。"""
    base = _public_api_base_or_raise()
    query = urlencode({"tenant_id": str(int(tenant_id))})
    return f"{base}/api/wx/open/authorize/callback?{query}"


def _register_pending_pre_auth(pre_auth_code: str, tenant_id: int, expires_in: int) -> None:
    """登记 pre_auth_code 与租户的临时映射，供授权事件推送兜底绑定。"""
    code = _s(pre_auth_code)
    if not code:
        return
    ttl = max(60, int(expires_in or 600))
    _pending_pre_auth_tenant[code] = (int(tenant_id), time.time() + ttl)


def pop_tenant_id_for_pre_auth(pre_auth_code: str | None) -> int | None:
    """取出并消费 pre_auth_code 对应的 tenant_id（过期则忽略）。"""
    code = _s(pre_auth_code)
    if not code:
        return None
    now = time.time()
    # 清理过期项，避免内存泄漏
    expired = [k for k, (_, exp) in _pending_pre_auth_tenant.items() if exp <= now]
    for k in expired:
        _pending_pre_auth_tenant.pop(k, None)
    item = _pending_pre_auth_tenant.pop(code, None)
    if item is None:
        return None
    tenant_id, exp = item
    if exp <= now:
        return None
    return int(tenant_id)


def create_tenant_pre_auth_link(db: Session, tenant_id: int) -> dict[str, Any]:
    """
    传统模式：向微信申请 pre_auth_code 并拼授权链接。

    商户在浏览器打开链接完成扫码授权后，微信会跳转 redirect_uri 并携带 auth_code；
    亦可由 component 回调推送 AuthorizationCode（需 pre_auth_code 映射仍在有效期内）。
    """
    from app.integrations.wechat_open_platform import get_component_access_token, wechat_open_platform_configured
    from app.models.tenant import Tenant

    if not wechat_open_platform_configured():
        raise HTTPException(status_code=503, detail="微信第三方平台 component 未配置")

    tenant = db.get(Tenant, int(tenant_id))
    if tenant is None:
        raise HTTPException(status_code=404, detail="租户不存在")

    ticket = get_component_verify_ticket(db)
    if not ticket:
        raise HTTPException(
            status_code=503,
            detail="component_verify_ticket 未就绪，请先配置回调或手动写入 ticket",
        )

    component_token = get_component_access_token(db)
    settings = get_settings()
    component_appid = _s(settings.WX_OPEN_COMPONENT_APPID)

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                CREATE_PREAUTH_URL,
                params={"component_access_token": component_token},
                json={"component_appid": component_appid},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("api_create_preauthcode 请求失败 tenant_id=%s", tenant_id)
        raise HTTPException(status_code=502, detail="微信 pre_auth_code 申请失败") from e

    if data.get("errcode") not in (None, 0):
        raise HTTPException(status_code=400, detail=str(data.get("errmsg") or "pre_auth_code 申请失败"))

    pre_auth_code = _s(data.get("pre_auth_code"))
    expires_in = int(data.get("expires_in") or 600)
    if not pre_auth_code:
        raise HTTPException(status_code=502, detail="微信未返回 pre_auth_code")

    _register_pending_pre_auth(pre_auth_code, int(tenant_id), expires_in)

    redirect_uri = build_tenant_authorize_redirect_uri(int(tenant_id))
    # auth_type=2：仅展示小程序授权（传统模式授权页）
    authorization_url = (
        f"{COMPONENT_LOGIN_PAGE_URL}?component_appid={quote(component_appid, safe='')}"
        f"&pre_auth_code={quote(pre_auth_code, safe='')}"
        f"&redirect_uri={quote(redirect_uri, safe='')}"
        f"&auth_type=2"
    )

    return {
        "tenant_id": int(tenant_id),
        "tenant_name": tenant.name,
        "pre_auth_code": pre_auth_code,
        "expires_in": expires_in,
        "redirect_uri": redirect_uri,
        "authorization_url": authorization_url,
        "mode_hint": "traditional",
    }


def exchange_authorization_code(db: Session, *, authorization_code: str, tenant_id: int) -> dict[str, Any]:
    """用授权码换取 authorizer token 并落库（授权完成回调或管理端手动触发）。"""
    from app.integrations.wechat_open_platform import get_component_access_token

    code = _s(authorization_code)
    if not code:
        raise HTTPException(status_code=400, detail="authorization_code 不能为空")

    component_token = get_component_access_token(db)
    settings = get_settings()
    component_appid = _s(settings.WX_OPEN_COMPONENT_APPID)

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                QUERY_AUTH_URL,
                params={"component_access_token": component_token},
                json={
                    "component_appid": component_appid,
                    "authorization_code": code,
                },
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("api_query_auth 请求失败")
        raise HTTPException(status_code=502, detail="微信授权码换取失败") from e

    if data.get("errcode") not in (None, 0):
        raise HTTPException(status_code=400, detail=str(data.get("errmsg") or "微信授权码无效"))

    info = data.get("authorization_info") or {}
    appid = _s(info.get("authorizer_appid"))
    access_token = _s(info.get("authorizer_access_token"))
    refresh_token = _s(info.get("authorizer_refresh_token"))
    expires_in = int(info.get("expires_in") or 7200)

    if not refresh_token:
        raise HTTPException(status_code=400, detail="微信未返回 authorizer_refresh_token")

    row = _integration_row_or_create(db, int(tenant_id))
    if appid:
        row.wx_mini_appid = appid
    row.wx_authorizer_access_token = access_token or None
    row.wx_authorizer_refresh_token = refresh_token
    row.wx_authorizer_token_expires_at = beijing_now_naive() + timedelta(seconds=max(60, expires_in - 120))
    row.wx_authorizer_authorized_at = beijing_now_naive()
    db.commit()
    logger.info("authorizer token 已落库 tenant_id=%s appid=%s", tenant_id, appid)
    return get_authorizer_admin_state(db, int(tenant_id))


def refresh_authorizer_access_token(db: Session, tenant_id: int) -> str:
    """刷新 authorizer_access_token；成功返回新 token。"""
    from app.integrations.wechat_open_platform import get_component_access_token

    row = get_tenant_integration_row(db, int(tenant_id))
    if row is None or not _s(row.wx_authorizer_refresh_token):
        raise WeChatMiniError("未配置 authorizer_refresh_token", status_code=503)

    appid = _s(row.wx_mini_appid)
    refresh_token = _s(row.wx_authorizer_refresh_token)
    if not appid:
        raise WeChatMiniError("未配置 authorizer_appid", status_code=503)

    component_token = get_component_access_token(db)
    settings = get_settings()
    component_appid = _s(settings.WX_OPEN_COMPONENT_APPID)

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                AUTHORIZER_TOKEN_URL,
                params={"component_access_token": component_token},
                json={
                    "component_appid": component_appid,
                    "authorizer_appid": appid,
                    "authorizer_refresh_token": refresh_token,
                },
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("api_authorizer_token 请求失败 tenant_id=%s", tenant_id)
        raise WeChatMiniError("刷新 authorizer token 失败", status_code=502) from e

    if data.get("errcode") not in (None, 0):
        msg = str(data.get("errmsg") or "未知错误")
        raise WeChatMiniError(f"刷新 authorizer token 失败: {msg}", status_code=400)

    access_token = _s(data.get("authorizer_access_token"))
    new_refresh = _s(data.get("authorizer_refresh_token"))
    expires_in = int(data.get("expires_in") or 7200)
    if not access_token:
        raise WeChatMiniError("微信未返回 authorizer_access_token", status_code=502)

    row.wx_authorizer_access_token = access_token
    if new_refresh:
        row.wx_authorizer_refresh_token = new_refresh
    row.wx_authorizer_token_expires_at = beijing_now_naive() + timedelta(seconds=max(60, expires_in - 120))
    row.wx_authorizer_authorized_at = beijing_now_naive()
    db.commit()
    return access_token


def get_valid_authorizer_access_token(db: Session, tenant_id: int) -> str:
    """获取可用 authorizer_access_token（将过期则自动刷新）。"""
    row = get_tenant_integration_row(db, int(tenant_id))
    if row is None or not _s(row.wx_authorizer_refresh_token):
        raise WeChatMiniError("未配置 authorizer token", status_code=503)

    now = beijing_now_naive()
    exp = row.wx_authorizer_token_expires_at
    token = _s(row.wx_authorizer_access_token)
    if token and exp is not None and exp > now + timedelta(minutes=3):
        return token
    return refresh_authorizer_access_token(db, int(tenant_id))


def lookup_tenant_id_by_authorizer_appid(db: Session, appid: str) -> int | None:
    """按代授权 AppID 反查 tenant_id。"""
    aid = _s(appid)
    if not aid:
        return None
    tid = db.scalar(
        select(TenantIntegrationSettings.tenant_id).where(
            TenantIntegrationSettings.wx_mini_appid == aid,
            TenantIntegrationSettings.wx_authorizer_refresh_token.isnot(None),
        )
    )
    return int(tid) if tid is not None else None
