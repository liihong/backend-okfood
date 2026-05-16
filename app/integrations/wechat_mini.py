import logging
import time
from datetime import date
from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import settings
from app.core.timeutil import now_shanghai

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

JSCODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
GET_PHONE_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"
SUBSCRIBE_SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"


class WeChatMiniError(Exception):
    """微信服务端返回错误或本地配置/解析失败。"""

    def __init__(
        self,
        message: str,
        *,
        errcode: int | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.errcode = errcode
        self.status_code = status_code


# appid -> (token, expires_at_unix)
_access_token_by_appid: dict[str, tuple[str, float]] = {}


def wx_mini_configured() -> bool:
    return bool(settings.WX_MINI_APPID.strip() and settings.WX_MINI_SECRET.strip())


def wx_mini_configured_for_tenant(db: "Session", tenant_id: int) -> bool:
    from app.services.tenant_integration_service import get_merged_wx_credentials

    a, s = get_merged_wx_credentials(db, int(tenant_id))
    return bool(a and s)


def _app_credentials() -> tuple[str, str]:
    appid = settings.WX_MINI_APPID.strip()
    secret = settings.WX_MINI_SECRET.strip()
    if not appid or not secret:
        raise WeChatMiniError("微信小程序未配置", status_code=503)
    return appid, secret


def _credentials_for_call(db: "Session | None", tenant_id: int | None) -> tuple[str, str]:
    if db is not None and tenant_id is not None:
        from app.services.tenant_integration_service import get_merged_wx_credentials

        appid, secret = get_merged_wx_credentials(db, int(tenant_id))
        if not appid or not secret:
            raise WeChatMiniError("微信小程序未配置（请配置租户对接或全局 WX_MINI_*）", status_code=503)
        return appid, secret
    return _app_credentials()


def jscode2session(js_code: str, *, db: "Session | None" = None, tenant_id: int | None = None) -> dict[str, Any]:
    """校验登录凭证，换取 openid / session_key（js_code 仅可使用一次）。"""
    appid, secret = _credentials_for_call(db, tenant_id)
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                JSCODE2SESSION_URL,
                params={
                    "appid": appid,
                    "secret": secret,
                    "js_code": js_code,
                    "grant_type": "authorization_code",
                },
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("微信 jscode2session 请求失败")
        raise WeChatMiniError("微信登录服务暂时不可用", status_code=502) from e

    errcode = data.get("errcode")
    if errcode not in (None, 0):
        msg = str(data.get("errmsg") or "未知错误")
        logger.warning("jscode2session 业务失败: errcode=%s errmsg=%s", errcode, msg)
        raise WeChatMiniError(
            f"登录凭证无效或已过期: {msg}",
            errcode=int(errcode) if errcode is not None else None,
        )
    if not data.get("openid"):
        raise WeChatMiniError("微信未返回用户标识")
    return data


def get_stable_access_token_for_app(appid: str, secret: str) -> str:
    """按小程序 appid 缓存 access_token（多租户下每个 AppId 独立）。"""
    aid = (appid or "").strip()
    sec = (secret or "").strip()
    if not aid or not sec:
        raise WeChatMiniError("微信小程序未配置", status_code=503)
    now = time.time()
    ent = _access_token_by_appid.get(aid)
    if ent and now < ent[1] - 120:
        return ent[0]
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                TOKEN_URL,
                params={
                    "grant_type": "client_credential",
                    "appid": aid,
                    "secret": sec,
                },
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("微信 access_token 请求失败")
        raise WeChatMiniError("微信服务暂时不可用", status_code=502) from e

    if data.get("errcode"):
        msg = str(data.get("errmsg") or "未知错误")
        raise WeChatMiniError(f"微信鉴权失败: {msg}", errcode=int(data["errcode"]), status_code=502)
    token = data.get("access_token")
    expires_in = int(data.get("expires_in") or 7200)
    if not token:
        raise WeChatMiniError("微信未返回 access_token", status_code=502)
    _access_token_by_appid[aid] = (str(token), now + expires_in)
    return str(token)


def get_stable_access_token() -> str:
    """兼容旧调用：仅使用全局 .env 中的单个小程序。"""
    appid, secret = _app_credentials()
    return get_stable_access_token_for_app(appid, secret)


def get_phone_pure_number(
    phone_code: str, *, db: "Session | None" = None, tenant_id: int | None = None
) -> str:
    """通过手机号动态令牌换取用户手机号。"""
    appid, secret = _credentials_for_call(db, tenant_id)
    access_token = get_stable_access_token_for_app(appid, secret)
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                f"{GET_PHONE_URL}?access_token={access_token}",
                json={"code": phone_code},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("微信 getuserphonenumber 请求失败")
        raise WeChatMiniError("获取手机号服务暂时不可用", status_code=502) from e

    info = data.get("phone_info")
    errcode = data.get("errcode")
    if not info and errcode not in (None, 0):
        msg = str(data.get("errmsg") or "未知错误")
        logger.warning("getuserphonenumber 业务失败: errcode=%s errmsg=%s", errcode, msg)
        raise WeChatMiniError(
            f"手机号授权无效或已过期: {msg}",
            errcode=int(errcode) if errcode is not None else None,
        )
    info = info or {}
    pure = str(info.get("purePhoneNumber") or "").strip()
    cc = str(info.get("countryCode") or "86").strip()
    if not pure:
        raise WeChatMiniError("未获取到手机号")
    if cc == "86":
        return pure
    return f"{cc}{pure}"


def _truncate_subscribe_value(text: str, *, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    if max_chars <= 1:
        return "…"
    return t[: max_chars - 1] + "…"


def send_subscribe_message(
    touser: str,
    template_id: str,
    *,
    page: str,
    data: dict[str, dict[str, str]],
    miniprogram_state: str = "formal",
    db: "Session | None" = None,
    tenant_id: int | None = None,
) -> dict[str, Any]:
    """调用订阅消息下发接口；成功返回微信 JSON；失败抛 WeChatMiniError。"""
    appid, secret = _credentials_for_call(db, tenant_id)
    access_token = get_stable_access_token_for_app(appid, secret)
    url = f"{SUBSCRIBE_SEND_URL}?access_token={access_token}"
    body: dict[str, Any] = {
        "touser": touser,
        "template_id": template_id,
        "page": page,
        "miniprogram_state": miniprogram_state,
        "lang": "zh_CN",
        "data": data,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
            out: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("微信 subscribe.send 请求失败")
        raise WeChatMiniError("订阅消息服务暂时不可用", status_code=502) from e

    errcode = out.get("errcode")
    if errcode not in (None, 0):
        msg = str(out.get("errmsg") or "未知错误")
        raise WeChatMiniError(msg, errcode=int(errcode) if errcode is not None else None, status_code=400)
    return out


def try_notify_member_delivery_confirmed(
    openid: str,
    *,
    delivery_date: date,
    title: str | None = None,
    detail: str = "配送员已确认，欢迎享用",
    db: "Session | None" = None,
    tenant_id: int | None = None,
) -> None:
    """会员订阅消息；未配置模板或未配置小程序时静默跳过。"""
    from app.services.tenant_integration_service import get_tenant_integration_row

    template_id = (settings.WX_MINI_SUBSCRIBE_DELIVERY_TMPL_ID or "").strip()
    if db is not None and tenant_id is not None:
        row = get_tenant_integration_row(db, int(tenant_id))
        if row and (row.wx_subscribe_delivery_tmpl_id or "").strip():
            template_id = (row.wx_subscribe_delivery_tmpl_id or "").strip()
    oid = (openid or "").strip()
    if not template_id or not oid:
        return
    if db is not None and tenant_id is not None:
        if not wx_mini_configured_for_tenant(db, int(tenant_id)):
            return
    elif not wx_mini_configured():
        return

    keys_raw = (settings.WX_MINI_SUBSCRIBE_DELIVERY_DATA_KEYS or "thing1,time2,thing3").strip()
    keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
    if not keys:
        keys = ["thing1", "time2", "thing3"]

    now = now_shanghai()
    time_str = now.strftime("%Y年%m月%d日 %H:%M")
    line1 = (title or "").strip() or f"{delivery_date.isoformat()} 餐品已送达"
    vals = [line1, time_str, detail]
    wrap: dict[str, dict[str, str]] = {}
    for i, k in enumerate(keys):
        raw = vals[i] if i < len(vals) else detail
        max_len = 32 if k.lower().startswith("time") else 20
        wrap[k] = {"value": _truncate_subscribe_value(raw, max_chars=max_len)}

    page = (settings.WX_MINI_SUBSCRIBE_PAGE or "pages/order/index").strip() or "pages/order/index"
    state = (settings.WX_MINI_SUBSCRIBE_MINIPROGRAM_STATE or "formal").strip() or "formal"
    try:
        send_subscribe_message(
            oid,
            template_id,
            page=page,
            data=wrap,
            miniprogram_state=state,
            db=db,
            tenant_id=tenant_id,
        )
    except WeChatMiniError as e:
        logger.warning(
            "送达订阅消息未送达: openid=%s… err=%s",
            oid[:6] if len(oid) > 6 else oid,
            e,
        )
    except Exception:
        logger.exception("送达订阅消息异常 member openid 前缀=%s", oid[:6] if len(oid) > 6 else oid)
