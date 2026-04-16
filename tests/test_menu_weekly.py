"""会员端周菜单接口：统一响应体与列表长度。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_weekly_menu_returns_envelope_and_seven_items():
    r = client.get("/api/menu/weekly")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 200
    assert isinstance(body["msg"], str)
    data = body["data"]
    assert "week_start" in data
    assert len(data["items"]) == 7
    first = data["items"][0]
    for key in ("date", "pic", "title", "desc", "dish_id", "slot"):
        assert key in first


def test_menu_detail_non_integer_dish_id_returns_422():
    r = client.get("/api/menu/detail/not-an-int")
    assert r.status_code == 422
