"""微信支付 v2：小程序 JSAPI 统一下单、回调验签（MD5 / HMAC-SHA256）。"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import secrets
import time
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import unquote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

UNIFIED_ORDER_URL = "https://api.mch.weixin.qq.com/pay/unifiedorder"


def wechat_pay_misconfiguration_detail() -> str | None:
    """若微信支付环境未就绪，返回可读原因；就绪则返回 None。"""
    mch = (settings.WECHAT_PAY_MCH_ID or "").strip()
    key = (settings.WECHAT_PAY_API_KEY or "").strip()
    notify = (settings.WECHAT_PAY_NOTIFY_URL or "").strip()
    appid = (settings.WX_MINI_APPID or "").strip()
    if not mch:
        return "未配置 WECHAT_PAY_MCH_ID（微信支付商户号）"
    if not key:
        return "未配置 WECHAT_PAY_API_KEY（商户平台「API 安全」中的 APIv2 密钥）"
    if len(key) != 32:
        return (
            f"WECHAT_PAY_API_KEY 必须为 32 位（微信 APIv2 密钥），当前 {len(key)} 位。"
            "请勿填入64 位 hex 或其它长度；请到 pay.weixin.qq.com 账户中心核对后重新设置"
        )
    if not notify:
        return "未配置 WECHAT_PAY_NOTIFY_URL（须为公网可访问的完整 URL，如 https://你的域名/api/pay/wechat/notify）"
    if not appid:
        return "未配置 WX_MINI_APPID（小程序 AppId）"
    return None


def wechat_pay_configured() -> bool:
    return wechat_pay_misconfiguration_detail() is None


def _api_key() -> str:
    return (settings.WECHAT_PAY_API_KEY or "").strip()


def _string_a(params: dict[str, Any]) -> str:
    pairs: list[str] = []
    for k in sorted(params.keys()):
        if k == "sign":
            continue
        v = params[k]
        if v is None or v == "":
            continue
        pairs.append(f"{k}={v}")
    return "&".join(pairs)


def sign_params_md5(params: dict[str, Any], api_key: str | None = None) -> str:
    key = api_key if api_key is not None else _api_key()
    s = f"{_string_a(params)}&key={key}"
    return hashlib.md5(s.encode("utf-8")).hexdigest().upper()


def sign_params_hmac_sha256(params: dict[str, Any], api_key: str | None = None) -> str:
    key = api_key if api_key is not None else _api_key()
    s = f"{_string_a(params)}&key={key}"
    return hmac.new(key.encode("utf-8"), s.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def verify_response_sign(data: dict[str, str]) -> bool:
    sign = (data.get("sign") or "").strip()
    if not sign:
        return False
    st = (data.get("sign_type") or "MD5").strip().upper()
    if st == "HMAC-SHA256":
        expect = sign_params_hmac_sha256(data)
    else:
        expect = sign_params_md5(data)
    return secrets.compare_digest(sign.upper(), expect.upper())


def dict_to_xml(params: dict[str, Any]) -> str:
    parts: list[str] = ["<xml>"]
    for k, v in sorted(params.items()):
        if v is None or v == "":
            continue
        parts.append(f"<{k}><![CDATA[{v}]]></{k}>")
    parts.append("</xml>")
    return "".join(parts)


def xml_to_dict(xml_raw: str) -> dict[str, str]:
    root = ET.fromstring(xml_raw)
    out: dict[str, str] = {}
    for child in root:
        tag = child.tag
        text = (child.text or "").strip()
        out[tag] = text
    return out


def random_nonce_str(n: int = 32) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def yuan_decimal_to_fen(amount_yuan) -> int:
    """Decimal / str 金额(元) -> 分，与微信 total_fee 一致。"""
    from decimal import Decimal, ROUND_HALF_UP

    d = amount_yuan if isinstance(amount_yuan, Decimal) else Decimal(str(amount_yuan))
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def unified_order_jsapi(
    *,
    out_trade_no: str,
    body: str,
    total_fee_fen: int,
    openid: str,
    spbill_create_ip: str,
) -> str:
    """统一下单 JSAPI，返回 prepay_id。失败抛 WeChatPayV2Error。"""
    cfg = wechat_pay_misconfiguration_detail()
    if cfg:
        raise WeChatPayV2Error(503, cfg)
    appid = (settings.WX_MINI_APPID or "").strip()
    mch_id = (settings.WECHAT_PAY_MCH_ID or "").strip()
    notify_url = (settings.WECHAT_PAY_NOTIFY_URL or "").strip()

    params: dict[str, Any] = {
        "appid": appid,
        "mch_id": mch_id,
        "nonce_str": random_nonce_str(),
        "body": body[:127] if body else "单次点餐",
        "out_trade_no": out_trade_no,
        "total_fee": str(int(total_fee_fen)),
        "spbill_create_ip": (spbill_create_ip or "127.0.0.1").strip()[:45],
        "notify_url": notify_url,
        "trade_type": "JSAPI",
        "openid": openid.strip(),
    }
    params["sign"] = sign_params_md5(params)

    xml_body = dict_to_xml(params)
    try:
        resp = httpx.post(
            UNIFIED_ORDER_URL,
            content=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=30.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("微信统一下单 HTTP 失败: %s", e)
        raise WeChatPayV2Error(502, "微信统一下单网络失败") from e

    text = resp.text
    data = xml_to_dict(text)
    if (data.get("return_code") or "").upper() != "SUCCESS":
        msg = data.get("return_msg") or "通信失败"
        logger.warning("微信统一下单 return_code 失败: %s", data)
        raise WeChatPayV2Error(502, f"微信接口：{msg}")
    if not verify_response_sign(data):
        logger.error("微信统一下单响应签名校验失败: %s", data)
        raise WeChatPayV2Error(502, "微信响应签名校验失败")
    if (data.get("result_code") or "").upper() != "SUCCESS":
        err = data.get("err_code_des") or data.get("err_code") or "下单失败"
        logger.warning("微信统一下单业务失败: %s", data)
        err_code = (data.get("err_code") or "").strip().upper()
        if err_code == "APPID_MCHID_NOT_MATCH" or "appid和mch_id不匹配" in str(err):
            err = (
                f"{err}。请在微信支付商户平台确认：发起支付的小程序 AppId（须与 .env 的 WX_MINI_APPID 一致）"
                "已关联当前商户号（.env 的 WECHAT_PAY_MCH_ID），勿混用其它小程序或公众号 AppId。"
            )
        raise WeChatPayV2Error(400, err)

    prepay_id = (data.get("prepay_id") or "").strip()
    if not prepay_id:
        raise WeChatPayV2Error(502, "微信未返回 prepay_id")
    return prepay_id


def build_miniprogram_pay_params(prepay_id: str) -> dict[str, str]:
    """生成小程序 wx.requestPayment / uni.requestPayment 所需字段。"""
    appid = (settings.WX_MINI_APPID or "").strip()
    time_stamp = str(int(time.time()))
    nonce_str = random_nonce_str()
    pkg = f"prepay_id={prepay_id}"
    sign_type = "MD5"
    pay_params: dict[str, Any] = {
        "appId": appid,
        "timeStamp": time_stamp,
        "nonceStr": nonce_str,
        "package": pkg,
        "signType": sign_type,
    }
    # 小程序支付签名：字段名区分大小写 appId、timeStamp、package、signType、nonceStr
    sign_src = {
        "appId": appid,
        "nonceStr": nonce_str,
        "package": pkg,
        "signType": sign_type,
        "timeStamp": time_stamp,
    }
    pay_sign = sign_params_md5(sign_src)
    pay_params["paySign"] = pay_sign
    return {k: str(v) for k, v in pay_params.items()}


def notify_client_ip_allowed(remote_ip: str) -> bool:
    raw = (settings.WECHAT_PAY_IP_WHITELIST or "").strip()
    if not raw:
        logger.warning("WECHAT_PAY_IP_WHITELIST 未配置，跳过微信支付回调 IP 校验（生产环境请务必配置）")
        return True
    ip = (remote_ip or "").strip()
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        try:
            if "/" in p:
                if addr in ipaddress.ip_network(p, strict=False):
                    return True
            elif ip == p:
                return True
        except ValueError:
            continue
    logger.warning("微信支付回调 IP 不在白名单: %s", ip)
    return False


def resolve_request_client_ip(forwarded_for: str | None, direct: str | None) -> str:
    if forwarded_for and forwarded_for.strip():
        first = forwarded_for.split(",")[0].strip()
        if first:
            return unquote(first)
    return (direct or "127.0.0.1").strip() or "127.0.0.1"


class WeChatPayV2Error(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)
