"""抖音 Webhooks：地址校验（verify_webhook）与事件推送。"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.douyin.config_service import resolve_douyin_client_secret_by_client_key

logger = logging.getLogger(__name__)


def _verify_douyin_webhook_signature(*, client_secret: str, raw_body: bytes, signature: str | None) -> bool:
    sig = (signature or "").strip()
    if not sig:
        return False
    expected = hashlib.sha1(client_secret.encode("utf-8") + raw_body).hexdigest()
    return hmac.compare_digest(sig.lower(), expected.lower())


def process_douyin_webhook(
    db: Session,
    raw_body: bytes,
    *,
    signature: str | None,
) -> tuple[int, dict[str, Any] | None]:
    """处理 Webhooks POST。返回 (status_code, response_body)；response_body 非空时原样 JSON 输出。"""
    if not raw_body:
        return 400, None
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, None
    if not isinstance(payload, dict):
        return 400, None

    event = str(payload.get("event") or "").strip()
    if event == "verify_webhook":
        content = payload.get("content")
        if not isinstance(content, dict) or "challenge" not in content:
            return 400, None
        return 200, {"challenge": content["challenge"]}

    settings = get_settings()
    skip_verify = bool(getattr(settings, "DOUYIN_WEBHOOK_SKIP_SIGN_VERIFY", False))
    if not skip_verify:
        client_key = str(payload.get("client_key") or "").strip()
        secret = resolve_douyin_client_secret_by_client_key(db, client_key)
        if not secret or not _verify_douyin_webhook_signature(
            client_secret=secret,
            raw_body=raw_body,
            signature=signature,
        ):
            logger.warning("抖音 Webhook 验签失败 event=%s client_key=%s", event, client_key)
            return 403, None

    logger.info(
        "抖音 Webhook 事件 event=%s client_key=%s log_id=%s",
        event or "-",
        payload.get("client_key"),
        payload.get("log_id"),
    )
    return 200, None
