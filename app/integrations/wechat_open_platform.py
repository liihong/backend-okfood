"""微信开放平台 · 第三方平台（component + authorizer）。

未配置或未落库 authorizer token 时，全链路回退租户直连 AppID/Secret（OK饭 现网不变）。
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import get_settings
from app.integrations.wechat_mini import WeChatMiniError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

COMPONENT_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/component/api_component_token"
AUTHORIZER_JSCODE2SESSION_URL = "https://api.weixin.qq.com/sns/component/jscode2session"

# component_access_token 内存缓存：(token, expires_at_unix)
_component_token_cache: tuple[str, float] | None = None


def wechat_open_platform_configured() -> bool:
    """是否已配置第三方平台 component 凭证。"""
    s = get_settings()
    return bool(_s(s.WX_OPEN_COMPONENT_APPID) and _s(s.WX_OPEN_COMPONENT_SECRET))


def _s(raw: str | None) -> str:
    return (raw or "").strip()


def get_component_access_token(db: "Session | None" = None) -> str:
    """
    获取 component_access_token：优先内存缓存，否则用 DB 中的 verify_ticket 向微信换取。

    verify_ticket 由 ``/api/wx/open/component/callback`` 或管理端手动写入。
    """
    global _component_token_cache
    if not wechat_open_platform_configured():
        raise WeChatMiniError("微信第三方平台未配置", status_code=503)

    now = time.time()
    if _component_token_cache is not None:
        token, exp = _component_token_cache
        if exp - now > 120:
            return token

    if db is None:
        from app.db.session import SessionLocal

        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        from app.services.shared.wx_open_authorizer_service import get_component_verify_ticket

        ticket = get_component_verify_ticket(db)
        if not ticket:
            raise WeChatMiniError(
                "component_verify_ticket 未就绪，请配置开放平台回调 URL 或在管理端手动写入 ticket",
                status_code=503,
            )

        s = get_settings()
        appid = _s(s.WX_OPEN_COMPONENT_APPID)
        secret = _s(s.WX_OPEN_COMPONENT_SECRET)

        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.post(
                    COMPONENT_TOKEN_URL,
                    json={
                        "component_appid": appid,
                        "component_appsecret": secret,
                        "component_verify_ticket": ticket,
                    },
                )
                r.raise_for_status()
                data: dict[str, Any] = r.json()
        except httpx.HTTPError as e:
            logger.exception("component_access_token 请求失败")
            raise WeChatMiniError("微信第三方平台服务暂时不可用", status_code=502) from e

        errcode = data.get("errcode")
        if errcode not in (None, 0):
            msg = str(data.get("errmsg") or "未知错误")
            logger.warning("component_access_token 失败: %s", msg)
            raise WeChatMiniError(f"第三方平台 token 获取失败: {msg}", status_code=503)

        token = _s(data.get("component_access_token"))
        expires_in = int(data.get("expires_in") or 7200)
        if not token:
            raise WeChatMiniError("微信未返回 component_access_token", status_code=503)

        _component_token_cache = (token, now + expires_in)
        return token
    finally:
        if close_db:
            db.close()


def jscode2session_via_authorizer(
    js_code: str,
    *,
    db: "Session | None" = None,
    tenant_id: int | None = None,
) -> dict[str, Any]:
    """
    小程序登录：优先第三方平台 component/jscode2session；否则直连 AppID/Secret。

    OK饭 主租户无 authorizer token 时，与改造前行为一致。
    """
    from app.integrations.wechat_mini import jscode2session
    from app.services.shared.tenant_integration_service import get_merged_wx_credentials

    if db is None or tenant_id is None:
        return jscode2session(js_code, db=db, tenant_id=tenant_id)

    from app.services.shared.wx_open_authorizer_service import tenant_has_authorizer_tokens

    if not (wechat_open_platform_configured() and tenant_has_authorizer_tokens(db, int(tenant_id))):
        return jscode2session(js_code, db=db, tenant_id=int(tenant_id))

    appid, _secret = get_merged_wx_credentials(db, int(tenant_id))
    if not appid:
        return jscode2session(js_code, db=db, tenant_id=int(tenant_id))

    try:
        from app.services.shared.wx_open_authorizer_service import get_valid_authorizer_access_token

        # component/jscode2session 使用 component_access_token，非 authorizer_access_token
        component_token = get_component_access_token(db)
        s = get_settings()
        component_appid = _s(s.WX_OPEN_COMPONENT_APPID)

        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                AUTHORIZER_JSCODE2SESSION_URL,
                params={
                    "appid": appid,
                    "js_code": js_code,
                    "grant_type": "authorization_code",
                    "component_appid": component_appid,
                    "component_access_token": component_token,
                },
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except WeChatMiniError:
        raise
    except httpx.HTTPError as e:
        logger.exception("component jscode2session 请求失败 tenant_id=%s", tenant_id)
        raise WeChatMiniError("微信登录服务暂时不可用", status_code=502) from e

    errcode = data.get("errcode")
    if errcode not in (None, 0):
        msg = str(data.get("errmsg") or "未知错误")
        logger.warning("component jscode2session 失败: errcode=%s %s", errcode, msg)
        # 第三方登录失败时回退直连，避免 SaaS 同时配置了 secret 时被卡死
        logger.info("component jscode2session 失败，回退直连 tenant_id=%s", tenant_id)
        return jscode2session(js_code, db=db, tenant_id=int(tenant_id))

    if not data.get("openid"):
        raise WeChatMiniError("微信未返回用户标识")

    # 预热 authorizer access_token 缓存（手机号等 API 使用）
    try:
        get_valid_authorizer_access_token(db, int(tenant_id))
    except WeChatMiniError:
        logger.debug("登录后预热 authorizer access_token 失败 tenant_id=%s", tenant_id)

    return data


def get_mini_program_api_access_token(db: "Session", tenant_id: int) -> tuple[str, str]:
    """
    获取小程序服务端 API 用的 access_token 及 appid。

    有 authorizer token 时用 authorizer_access_token；否则 client_credential。
    """
    from app.integrations.wechat_mini import get_stable_access_token_for_app
    from app.services.shared.tenant_integration_service import get_merged_wx_credentials
    from app.services.shared.wx_open_authorizer_service import (
        get_valid_authorizer_access_token,
        tenant_has_authorizer_tokens,
    )

    appid, secret = get_merged_wx_credentials(db, int(tenant_id))
    if not appid:
        raise WeChatMiniError("微信小程序未配置", status_code=503)

    if wechat_open_platform_configured() and tenant_has_authorizer_tokens(db, int(tenant_id)):
        token = get_valid_authorizer_access_token(db, int(tenant_id))
        return appid, token

    if not secret:
        raise WeChatMiniError("微信小程序 Secret 未配置", status_code=503)
    return appid, get_stable_access_token_for_app(appid, secret)
