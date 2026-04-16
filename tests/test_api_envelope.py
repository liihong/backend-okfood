"""校验统一响应体与基础路由行为。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_envelope():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 200
    assert body["data"] == {"status": "ok"}
    assert isinstance(body["msg"], str)


def test_validation_error_returns_envelope():
    r = client.post("/api/user/sms/send", json={})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == 422
    assert body["data"] is None
    assert isinstance(body["msg"], str)
