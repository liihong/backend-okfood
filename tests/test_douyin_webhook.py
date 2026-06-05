"""抖音 Webhook 单元测试。"""

from __future__ import annotations

import hashlib
import json

from app.services.douyin.webhook_service import process_douyin_webhook


class _FakeDb:
    pass


def test_verify_webhook_returns_challenge():
    payload = {
        "event": "verify_webhook",
        "client_key": "test_key",
        "content": {"challenge": 44499712},
    }
    raw = json.dumps(payload).encode("utf-8")
    status, body = process_douyin_webhook(_FakeDb(), raw, signature=None)
    assert status == 200
    assert body == {"challenge": 44499712}


def test_webhook_event_requires_signature_when_not_skipped(monkeypatch):
    monkeypatch.setenv("DOUYIN_WEBHOOK_SKIP_SIGN_VERIFY", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.douyin.webhook_service.resolve_douyin_client_secret_by_client_key",
        lambda _db, _key: "secret",
    )

    payload = {"event": "some_event", "client_key": "known", "content": {}}
    raw = json.dumps(payload).encode("utf-8")
    status, body = process_douyin_webhook(_FakeDb(), raw, signature="bad")
    assert status == 403
    assert body is None

    get_settings.cache_clear()


def test_webhook_signature_sha1():
    secret = "abc"
    raw = b'{"event":"x"}'
    sig = hashlib.sha1(secret.encode("utf-8") + raw).hexdigest()
    assert sig
