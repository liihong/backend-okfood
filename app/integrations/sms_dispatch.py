import json
import logging

import httpx
from alibabacloud_dysmsapi20170525 import models as dysms_models
from alibabacloud_dysmsapi20170525.client import Client as DysmsClient
from alibabacloud_tea_openapi import models as open_api_models

from app.core.config import Settings

logger = logging.getLogger(__name__)


class SmsDispatchError(Exception):
    """短信通道调用失败（网络、鉴权、运营商返回错误等）。"""


def dispatch_login_code(phone: str, code: str, settings: Settings) -> None:
    """
    发送登录验证码：按 SMS_PROVIDER 走阿里云或自建 Webhook。
    Webhook 约定：POST JSON {"phone": "<手机号>", "code": "<6位>"}，可选 Authorization: Bearer <SMS_WEBHOOK_TOKEN>。
    阿里云模板参数名需为 code（与 template_param JSON 一致）。
    """
    if settings.SMS_PROVIDER == "webhook":
        _send_webhook(phone, code, settings)
        return
    if settings.SMS_PROVIDER == "aliyun":
        _send_aliyun(phone, code, settings)
        return
    raise SmsDispatchError(f"不支持的 SMS_PROVIDER: {settings.SMS_PROVIDER}")


def _send_webhook(phone: str, code: str, settings: Settings) -> None:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = settings.SMS_WEBHOOK_TOKEN.strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(settings.SMS_WEBHOOK_URL, json={"phone": phone, "code": code}, headers=headers)
            r.raise_for_status()
    except Exception as e:
        logger.exception("短信 Webhook 调用失败")
        raise SmsDispatchError("短信 Webhook 调用失败") from e


def _send_aliyun(phone: str, code: str, settings: Settings) -> None:
    try:
        cfg = open_api_models.Config(
            access_key_id=settings.ALIYUN_ACCESS_KEY_ID,
            access_key_secret=settings.ALIYUN_ACCESS_KEY_SECRET,
        )
        cfg.endpoint = settings.ALIYUN_SMS_ENDPOINT
        client = DysmsClient(cfg)
        req = dysms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=settings.ALIYUN_SMS_SIGN_NAME,
            template_code=settings.ALIYUN_SMS_TEMPLATE_CODE,
            template_param=json.dumps({"code": code}),
        )
        resp = client.send_sms(req)
        body = resp.body
        if body is None or getattr(body, "code", None) != "OK":
            msg = getattr(body, "message", None) if body else None
            raise SmsDispatchError(msg or "阿里云短信返回非 OK")
    except SmsDispatchError:
        raise
    except Exception as e:
        logger.exception("阿里云短信发送失败")
        raise SmsDispatchError("阿里云短信发送失败") from e
