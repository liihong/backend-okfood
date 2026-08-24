"""微信支付 v2：小程序 JSAPI 统一下单、回调验签（MD5 / HMAC-SHA256）。"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import secrets
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

UNIFIED_ORDER_URL = "https://api.mch.weixin.qq.com/pay/unifiedorder"
ORDER_QUERY_URL = "https://api.mch.weixin.qq.com/pay/orderquery"
CLOSE_ORDER_URL = "https://api.mch.weixin.qq.com/pay/closeorder"
REFUND_URL = "https://api.mch.weixin.qq.com/secapi/pay/refund"


def wechat_pay_misconfiguration_detail() -> str | None:
    """主租户 OK饭 直连凭证是否就绪。"""
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


def _global_direct_pay_config() -> Any:
    """无租户上下文时回落主租户直连 .env。"""
    from app.services.shared.tenant_integration_service import MergedPayConfig

    return MergedPayConfig(
        wx_mini_appid=(settings.WX_MINI_APPID or "").strip(),
        wechat_pay_mch_id=(settings.WECHAT_PAY_MCH_ID or "").strip(),
        wechat_pay_api_key=(settings.WECHAT_PAY_API_KEY or "").strip(),
        wechat_pay_notify_url=(settings.WECHAT_PAY_NOTIFY_URL or "").strip(),
        wechat_pay_ssl_cert_path=(settings.WECHAT_PAY_SSL_CERT_PATH or "").strip(),
        wechat_pay_ssl_key_path=(settings.WECHAT_PAY_SSL_KEY_PATH or "").strip(),
    )


def partner_base_params(cfg: Any) -> dict[str, str]:
    """服务商接口公共字段：appid/mch_id 为服务商，sub_* 为特约商户。"""
    return {
        "appid": (getattr(cfg, "wechat_pay_sp_appid", None) or "").strip(),
        "mch_id": (getattr(cfg, "wechat_pay_sp_mch_id", None) or "").strip(),
        "sub_mch_id": (getattr(cfg, "wechat_pay_mch_id", None) or "").strip(),
        "sub_appid": (getattr(cfg, "wx_mini_appid", None) or "").strip(),
    }


def pay_trade_base_params(cfg: Any, *, openid: str | None = None) -> dict[str, str]:
    """按配置选择直连或服务商下单字段。"""
    from app.services.shared.tenant_integration_service import is_partner_pay_config

    if is_partner_pay_config(cfg):
        out = partner_base_params(cfg)
        if openid is not None:
            out["sub_openid"] = openid.strip()
        return out
    out = {
        "appid": (getattr(cfg, "wx_mini_appid", None) or "").strip(),
        "mch_id": (getattr(cfg, "wechat_pay_mch_id", None) or "").strip(),
    }
    if openid is not None:
        out["openid"] = openid.strip()
    return out


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


@dataclass(frozen=True)
class WechatPayNotifyParsed:
    """支付结果通知中已通过验签与基础字段校验的数据。"""

    out_trade_no: str
    transaction_id: str
    total_fee: int


def parse_wechat_pay_notify(
    data: dict[str, str],
    *,
    db: Any | None = None,
) -> tuple[bool, str, WechatPayNotifyParsed | None]:
    """校验微信异步通知签名与 return/result_code，解析 out_trade_no、transaction_id、total_fee（分）。"""
    if (data.get("return_code") or "").upper() != "SUCCESS":
        return False, (data.get("return_msg") or "return_fail")[:200], None
    # 多租户：按订单/mch_id/各租户密钥依次尝试验签，禁止未命中订单时仅用主租户密钥
    if db is not None:
        from app.services.shared.tenant_integration_service import (
            resolve_wechat_pay_notify_api_key_candidates,
        )

        candidates = resolve_wechat_pay_notify_api_key_candidates(db, data)
        for api_key in candidates:
            if verify_response_sign(data, api_key=api_key):
                break
        else:
            logger.error(
                "微信回调签名校验失败（已尝试 %s 组租户密钥）: %s",
                len(candidates),
                {k: data.get(k) for k in ("out_trade_no", "mch_id", "result_code")},
            )
            return False, "sign", None
    elif not verify_response_sign(data, api_key=None):
        logger.error("微信回调签名校验失败: %s", {k: data.get(k) for k in ("out_trade_no", "result_code")})
        return False, "sign", None
    if (data.get("result_code") or "").upper() != "SUCCESS":
        return False, (data.get("err_code_des") or data.get("err_code") or "result_fail")[:200], None

    out_no = (data.get("out_trade_no") or "").strip()
    tx_id = (data.get("transaction_id") or "").strip()
    fee_s = (data.get("total_fee") or "").strip()
    if not out_no or not fee_s:
        return False, "missing_field", None
    try:
        total_fee = int(fee_s)
    except ValueError:
        return False, "total_fee", None
    return True, "", WechatPayNotifyParsed(out_trade_no=out_no, transaction_id=tx_id, total_fee=total_fee)


def verify_response_sign(data: dict[str, str], api_key: str | None = None) -> bool:
    sign = (data.get("sign") or "").strip()
    if not sign:
        return False
    st = (data.get("sign_type") or "MD5").strip().upper()
    key = (api_key if api_key is not None else _api_key()).strip()
    if st == "HMAC-SHA256":
        expect = sign_params_hmac_sha256(data, api_key=key)
    else:
        expect = sign_params_md5(data, api_key=key)
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
    pay: Any | None = None,
) -> str:
    """统一下单 JSAPI：主租户直连，加盟租户服务商。``pay`` 为空时回落 OK饭 .env。"""
    from app.services.shared.tenant_integration_service import (
        is_partner_pay_config,
        wechat_pay_misconfiguration_detail_merged,
    )

    cfg = pay if pay is not None else _global_direct_pay_config()
    perr = wechat_pay_misconfiguration_detail_merged(cfg)
    if perr:
        raise WeChatPayV2Error(503, perr)
    notify_url = cfg.wechat_pay_notify_url
    api_key = cfg.wechat_pay_api_key

    params: dict[str, Any] = {
        **pay_trade_base_params(cfg, openid=openid),
        "nonce_str": random_nonce_str(),
        "body": body[:127] if body else "单次点餐",
        "out_trade_no": out_trade_no,
        "total_fee": str(int(total_fee_fen)),
        "spbill_create_ip": (spbill_create_ip or "127.0.0.1").strip()[:45],
        "notify_url": notify_url,
        "trade_type": "JSAPI",
    }
    params["sign"] = sign_params_md5(params, api_key=api_key)

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
    if not verify_response_sign(data, api_key=api_key):
        logger.error("微信统一下单响应签名校验失败: %s", data)
        raise WeChatPayV2Error(502, "微信响应签名校验失败")
    if (data.get("result_code") or "").upper() != "SUCCESS":
        err = data.get("err_code_des") or data.get("err_code") or "下单失败"
        logger.warning("微信统一下单业务失败: %s", data)
        err_code = (data.get("err_code") or "").strip().upper()
        if err_code == "APPID_MCHID_NOT_MATCH" or "appid和mch_id不匹配" in str(err):
            if is_partner_pay_config(cfg):
                err = (
                    f"{err}。请在服务商后台「特约商户 APPID 配置」绑定本店小程序 AppId，"
                    "并确认 .env 的 WECHAT_PAY_SP_APPID 为服务商 AppId、租户对接中的特约商户号正确。"
                )
            else:
                err = (
                    f"{err}。请在微信支付商户平台确认：发起支付的小程序 AppId（须与 .env 的 WX_MINI_APPID 一致）"
                    "已关联当前商户号（.env 的 WECHAT_PAY_MCH_ID），勿混用其它小程序或公众号 AppId。"
                )
        raise WeChatPayV2Error(400, err)

    prepay_id = (data.get("prepay_id") or "").strip()
    if not prepay_id:
        raise WeChatPayV2Error(502, "微信未返回 prepay_id")
    return prepay_id


def query_order_by_out_trade_no(out_trade_no: str, *, pay: Any | None = None) -> dict[str, str]:
    """
    调用微信支付 v2「查询订单」，成功返回与通知类似的字段（需对返回验签）。

    用于异步通知未达服务端时，由小程序主动拉单完成入账（与 /pay/wechat/notify 等效验签后字段）。
    """
    from app.services.shared.tenant_integration_service import wechat_pay_misconfiguration_detail_merged

    cfg = pay if pay is not None else _global_direct_pay_config()
    perr = wechat_pay_misconfiguration_detail_merged(cfg)
    if perr:
        raise WeChatPayV2Error(503, perr)
    otn = (out_trade_no or "").strip()[:32]
    if not otn:
        raise WeChatPayV2Error(400, "缺少商户单号")
    api_key = cfg.wechat_pay_api_key
    params: dict[str, Any] = {
        **pay_trade_base_params(cfg),
        "out_trade_no": otn,
        "nonce_str": random_nonce_str(),
    }
    params["sign"] = sign_params_md5(params, api_key=api_key)
    xml_body = dict_to_xml(params)
    try:
        resp = httpx.post(
            ORDER_QUERY_URL,
            content=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("微信 orderquery 网络失败: %s", e)
        raise WeChatPayV2Error(502, "微信查询订单网络失败") from e
    data = xml_to_dict(resp.text)
    if (data.get("return_code") or "").upper() != "SUCCESS":
        msg = (data.get("return_msg") or "通信失败")[:200]
        raise WeChatPayV2Error(502, f"微信查询订单：{msg}")
    if not verify_response_sign(data, api_key=api_key):
        logger.error("微信 orderquery 响应签名校验失败: %s", {k: data.get(k) for k in data.keys() if k != "sign"})
        raise WeChatPayV2Error(502, "微信查询订单响应签名校验失败")
    return data


def close_order_by_out_trade_no(out_trade_no: str, *, pay: Any | None = None) -> dict[str, str]:
    """
    关闭未支付的微信订单（换券改价、统一下单重入失败等场景需先关单再换新商户单号）。

    若订单不存在或已关闭，视为成功（幂等）。
    """
    from app.services.shared.tenant_integration_service import wechat_pay_misconfiguration_detail_merged

    cfg = pay if pay is not None else _global_direct_pay_config()
    perr = wechat_pay_misconfiguration_detail_merged(cfg)
    if perr:
        raise WeChatPayV2Error(503, perr)
    otn = (out_trade_no or "").strip()[:32]
    if not otn:
        raise WeChatPayV2Error(400, "缺少商户单号")
    api_key = cfg.wechat_pay_api_key
    params: dict[str, Any] = {
        **pay_trade_base_params(cfg),
        "out_trade_no": otn,
        "nonce_str": random_nonce_str(),
    }
    params["sign"] = sign_params_md5(params, api_key=api_key)
    xml_body = dict_to_xml(params)
    try:
        resp = httpx.post(
            CLOSE_ORDER_URL,
            content=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("微信 closeorder 网络失败: %s", e)
        raise WeChatPayV2Error(502, "微信关单网络失败") from e
    data = xml_to_dict(resp.text)
    if (data.get("return_code") or "").upper() != "SUCCESS":
        msg = (data.get("return_msg") or "通信失败")[:200]
        raise WeChatPayV2Error(502, f"微信关单：{msg}")
    if not verify_response_sign(data, api_key=api_key):
        logger.error("微信 closeorder 响应签名校验失败")
        raise WeChatPayV2Error(502, "微信关单响应签名校验失败")
    if (data.get("result_code") or "").upper() != "SUCCESS":
        err_c = (data.get("err_code") or "").strip().upper()
        # 订单不存在 / 已关单：视为关单目标已达成
        if err_c in ("ORDERNOTEXIST", "ORDERCLOSED"):
            return data
        err = (data.get("err_code_des") or data.get("err_code") or "关单失败")[:200]
        raise WeChatPayV2Error(400, f"微信：{err}")
    return data


def _secapi_ssl_cert_paths(*, pay: Any | None = None) -> tuple[str, str]:
    """退款证书：优先 MergedPayConfig（主租户直连 / 加盟服务商已按模式合并），否则 OK饭 .env。"""
    c = ""
    k = ""
    if pay is not None:
        c = (getattr(pay, "wechat_pay_ssl_cert_path", None) or "").strip()
        k = (getattr(pay, "wechat_pay_ssl_key_path", None) or "").strip()
    if not c:
        c = (settings.WECHAT_PAY_SSL_CERT_PATH or "").strip()
    if not k:
        k = (settings.WECHAT_PAY_SSL_KEY_PATH or "").strip()
    if not c or not k:
        raise WeChatPayV2Error(
            503,
            "未配置微信退款 API 证书路径：主租户请配置 WECHAT_PAY_SSL_*，"
            "加盟租户请配置 WECHAT_PAY_SP_SSL_CERT_PATH / WECHAT_PAY_SP_SSL_KEY_PATH（服务商证书）",
        )
    cp = Path(c)
    kp = Path(k)
    if not cp.is_file() or not kp.is_file():
        raise WeChatPayV2Error(503, "微信支付 API 证书路径无效或文件不存在（请确认路径指向服务器可读文件）")
    return str(cp.resolve()), str(kp.resolve())


def refund_order_v2(
    *,
    out_trade_no: str,
    out_refund_no: str,
    total_fee_fen: int,
    refund_fee_fen: int,
    pay: Any | None = None,
    transaction_id: str | None = None,
) -> dict[str, str]:
    """
    微信支付 v2 申请退款（原路退至支付用户）。需配置 SSL 商户证书。

    ``out_trade_no`` 与 ``transaction_id`` 至少其一必填（此处一般以商户单号为主）。
    """
    from app.services.shared.tenant_integration_service import (
        is_partner_pay_config,
        wechat_pay_misconfiguration_detail_merged,
    )

    cfg = pay if pay is not None else _global_direct_pay_config()
    perr = wechat_pay_misconfiguration_detail_merged(cfg)
    if perr:
        raise WeChatPayV2Error(503, perr)
    otn = (out_trade_no or "").strip()[:32]
    orn = (out_refund_no or "").strip()[:32]
    tx = (transaction_id or "").strip()
    if not otn and not tx:
        raise WeChatPayV2Error(400, "缺少商户单号与微信订单号")
    if not orn:
        raise WeChatPayV2Error(400, "缺少商户退款单号")
    tf = int(total_fee_fen)
    rf = int(refund_fee_fen)
    if tf <= 0 or rf <= 0 or rf > tf:
        raise WeChatPayV2Error(400, "退款金额不合法")

    cert_pair = _secapi_ssl_cert_paths(pay=cfg)
    api_key = cfg.wechat_pay_api_key
    op_mch = (
        (getattr(cfg, "wechat_pay_sp_mch_id", None) or "").strip()
        if is_partner_pay_config(cfg)
        else (getattr(cfg, "wechat_pay_mch_id", None) or "").strip()
    )
    params: dict[str, Any] = {
        **pay_trade_base_params(cfg),
        "nonce_str": random_nonce_str(),
        "out_refund_no": orn,
        "total_fee": str(tf),
        "refund_fee": str(rf),
        "op_user_id": op_mch,
    }
    if otn:
        params["out_trade_no"] = otn
    if tx:
        params["transaction_id"] = tx
    params["sign"] = sign_params_md5(params, api_key=api_key)
    xml_body = dict_to_xml(params)
    try:
        with httpx.Client(verify=True, cert=cert_pair, timeout=30.0) as client:
            resp = client.post(
                REFUND_URL,
                content=xml_body.encode("utf-8"),
                headers={"Content-Type": "application/xml"},
            )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("微信 refund HTTP 失败: %s", e)
        raise WeChatPayV2Error(502, "微信退款接口网络失败") from e
    data = xml_to_dict(resp.text)
    if (data.get("return_code") or "").upper() != "SUCCESS":
        msg = (data.get("return_msg") or "通信失败")[:200]
        raise WeChatPayV2Error(502, f"微信退款：{msg}")
    if not verify_response_sign(data, api_key=api_key):
        logger.error("微信 refund 响应签名校验失败")
        raise WeChatPayV2Error(502, "微信退款响应签名校验失败")
    if (data.get("result_code") or "").upper() != "SUCCESS":
        err = (data.get("err_code_des") or data.get("err_code") or "退款失败")[:200]
        raise WeChatPayV2Error(400, f"微信：{err}")
    return data


def build_miniprogram_pay_params(
    prepay_id: str,
    *,
    appid: str | None = None,
    api_key: str | None = None,
) -> dict[str, str]:
    """生成小程序 wx.requestPayment / uni.requestPayment 所需字段。"""
    aid = ((appid if appid is not None else settings.WX_MINI_APPID) or "").strip()
    key = api_key if api_key is not None else _api_key()
    time_stamp = str(int(time.time()))
    nonce_str = random_nonce_str()
    pkg = f"prepay_id={prepay_id}"
    sign_type = "MD5"
    pay_params: dict[str, Any] = {
        "appId": aid,
        "timeStamp": time_stamp,
        "nonceStr": nonce_str,
        "package": pkg,
        "signType": sign_type,
    }
    # 小程序支付签名：字段名区分大小写 appId、timeStamp、package、signType、nonceStr
    sign_src = {
        "appId": aid,
        "nonceStr": nonce_str,
        "package": pkg,
        "signType": sign_type,
        "timeStamp": time_stamp,
    }
    pay_sign = sign_params_md5(sign_src, api_key=key)
    pay_params["paySign"] = pay_sign
    return {k: str(v) for k, v in pay_params.items()}


# 微信支付官方「回调通知注意事项」出口网段；与 .env 白名单取并集，避免漏配深圳/香港等段导致已扣款不入账。
WECHAT_PAY_OFFICIAL_NOTIFY_NETWORKS: tuple[str, ...] = (
    "101.226.103.0/25",
    "140.207.54.0/25",
    "121.51.58.128/25",
    "183.3.234.0/25",
    "58.251.80.0/25",
    "121.51.30.128/25",
    "203.205.219.128/25",
    "81.71.199.64/32",
    "81.71.198.25/32",
    "81.71.199.59/32",
    "182.254.48.0/24",
)


def _ip_in_allow_parts(addr: ipaddress.IPv4Address | ipaddress.IPv6Address, parts: list[str]) -> bool:
    ip_s = str(addr)
    for p in parts:
        if not p:
            continue
        try:
            if "/" in p:
                if addr in ipaddress.ip_network(p, strict=False):
                    return True
            elif ip_s == p:
                return True
        except ValueError:
            continue
    return False


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
    env_parts = [p.strip() for p in raw.split(",") if p.strip()]
    official_parts = list(WECHAT_PAY_OFFICIAL_NOTIFY_NETWORKS)
    if _ip_in_allow_parts(addr, official_parts) or _ip_in_allow_parts(addr, env_parts):
        return True
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
