import logging
import time
from datetime import date
from typing import Any

import httpx

from app.core.config import settings
from app.core.timeutil import now_shanghai

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


_access_token: str | None = None
_access_token_expires_at: float = 0.0


def wx_mini_configured() -> bool:
    return bool(settings.WX_MINI_APPID.strip() and settings.WX_MINI_SECRET.strip())


def _app_credentials() -> tuple[str, str]:
    appid = settings.WX_MINI_APPID.strip()
    secret = settings.WX_MINI_SECRET.strip()
    if not appid or not secret:
        raise WeChatMiniError("微信小程序未配置", status_code=503)
    return appid, secret


def jscode2session(js_code: str) -> dict[str, Any]:
    """校验登录凭证，换取 openid / session_key（js_code 仅可使用一次）。"""
    appid, secret = _app_credentials()
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
        raise WeChatMiniError(f"登录凭证无效或已过期: {msg}", errcode=int(errcode) if errcode is not None else None)
    if not data.get("openid"):
        raise WeChatMiniError("微信未返回用户标识")
    return data


def get_stable_access_token() -> str:
    """小程序全局 access_token（带简单进程内缓存）。"""
    global _access_token, _access_token_expires_at
    appid, secret = _app_credentials()
    now = time.time()
    if _access_token and now < _access_token_expires_at - 120:
        return _access_token
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                TOKEN_URL,
                params={
                    "grant_type": "client_credential",
                    "appid": appid,
                    "secret": secret,
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
    _access_token = str(token)
    _access_token_expires_at = now + expires_in
    return _access_token


def get_phone_pure_number(phone_code: str) -> str:
    """通过手机号动态令牌换取用户手机号（与会员库 phone 主键一致：86 号段为11 位国内号码）。"""
    access_token = get_stable_access_token()
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
) -> dict[str, Any]:
    """调用订阅消息下发接口；成功返回微信 JSON；失败抛 WeChatMiniError。"""
    access_token = get_stable_access_token()
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
) -> None:
    """
    会员曾在前端授权对应模板后，服务端可下发一条订阅消息；未配置模板、无 openid、或用户未授权时静默跳过。
    """
    template_id = (settings.WX_MINI_SUBSCRIBE_DELIVERY_TMPL_ID or "").strip()
    oid = (openid or "").strip()
    if not template_id or not oid:
        return
    if not wx_mini_configured():
        return

    keys_raw = (settings.WX_MINI_SUBSCRIBE_DELIVERY_DATA_KEYS or "thing1,time2,thing3").strip()
    keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
    if not keys:
        keys = ["thing1", "time2", "thing3"]

    now = now_shanghai()
    time_str = now.strftime("%Y年%m月%d日 %H:%M")
    line1 = (title or "").strip() or f"{delivery_date.isoformat()} 餐品已送达"
    vals = [line1, time_str, detail]
    data: dict[str, dict[str, str]] = {}
    for i, k in enumerate(keys):
        raw = vals[i] if i < len(vals) else detail
        max_len = 32 if k.lower().startswith("time") else 20
        data[k] = {"value": _truncate_subscribe_value(raw, max_chars=max_len)}

    page = (settings.WX_MINI_SUBSCRIBE_PAGE or "pages/order/index").strip() or "pages/order/index"
    state = (settings.WX_MINI_SUBSCRIBE_MINIPROGRAM_STATE or "formal").strip() or "formal"
    try:
        send_subscribe_message(
            oid,
            template_id,
            page=page,
            data=data,
            miniprogram_state=state,
        )
    except WeChatMiniError as e:
        # 43101 用户未订阅/次数用完等，不影响送达主流程
        logger.warning(
            "送达订阅消息未送达: openid=%s… err=%s",
            oid[:6] if len(oid) > 6 else oid,
            e,
        )
    except Exception:
        logger.exception("送达订阅消息异常 member openid 前缀=%s", oid[:6] if len(oid) > 6 else oid)
