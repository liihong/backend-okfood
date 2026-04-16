"""管理端配送员接口：SQLite 全表 + 区域聚合。"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 —注册 metadata
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin_user import AdminUser
from app.models.member import Member
from app.models.member_address import MemberAddress


@pytest.fixture
def admin_full_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with SessionLocal() as db:
        db.add(
            AdminUser(
                username="admin",
                password_hash=hash_password("admin123"),
                is_active=True,
            )
        )
        db.commit()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client, SessionLocal
    app.dependency_overrides.pop(get_db, None)


def _admin_token(client: TestClient) -> str:
    r = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert r.status_code == 200
    return r.json()["data"]["access_token"]


def test_admin_courier_list_create_patch_pin_regions(admin_full_client):
    c, _ = admin_full_client
    token = _admin_token(c)
    headers = {"Authorization": f"Bearer {token}"}

    r = c.post(
        "/api/admin/couriers",
        json={
            "courier_id": "K01",
            "name": "老王",
            "phone": "13800000000",
            "pin": "123456",
            "is_active": True,
        },
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 200
    d = body["data"]
    assert d["courier_id"] == "K01"
    assert d["phone"] == "13800000000"
    assert d["regions"] == []

    tri = [[121.0, 31.0], [121.1, 31.0], [121.05, 31.1]]
    r = c.post(
        "/api/admin/delivery-regions",
        json={
            "name": "东区",
            "polygon_json": tri,
            "couriers": [{"courier_id": "K01", "is_primary": True, "sort_order": 0}],
        },
        headers=headers,
    )
    assert r.status_code == 200

    r = c.get("/api/admin/couriers", headers=headers)
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) == 1
    row = items[0]
    assert row["courier_id"] == "K01"
    assert len(row["regions"]) == 1
    assert row["regions"][0]["name"] == "东区"
    assert row["regions"][0]["is_primary"] is True

    r = c.patch(
        "/api/admin/couriers/K01",
        json={"fee_pending": "100.5", "fee_settled": "20.25"},
        headers=headers,
    )
    assert r.status_code == 200
    d = r.json()["data"]
    assert float(d["fee_pending"]) == 100.5
    assert float(d["fee_settled"]) == 20.25

    r = c.post(
        "/api/admin/couriers/K01/pin",
        json={"pin": "654321"},
        headers=headers,
    )
    assert r.status_code == 200

    r = c.post("/api/courier/login", json={"courier_id": "K01", "pin": "654321"})
    assert r.status_code == 200
    assert r.json()["data"]["access_token"]


def test_courier_login_phone_tasks_scoped_to_assigned_regions(admin_full_client):
    client, SessionLocal = admin_full_client
    token = _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    tri = [[121.0, 31.0], [121.1, 31.0], [121.05, 31.1]]

    r = client.post(
        "/api/admin/couriers",
        json={
            "courier_id": "Kz",
            "name": "片区专送",
            "phone": "13900000007",
            "pin": "123456",
            "is_active": True,
        },
        headers=headers,
    )
    assert r.status_code == 200

    r = client.post(
        "/api/admin/delivery-regions",
        json={"name": "东区", "polygon_json": tri, "couriers": []},
        headers=headers,
    )
    assert r.status_code == 200

    r = client.post(
        "/api/admin/delivery-regions",
        json={
            "name": "西区",
            "polygon_json": tri,
            "couriers": [{"courier_id": "Kz", "is_primary": True, "sort_order": 0}],
        },
        headers=headers,
    )
    assert r.status_code == 200

    d = date(2026, 7, 15)
    with SessionLocal() as db:
        m_east = Member(
            phone="13800000011",
            name="东用户",
            balance=2,
            is_active=True,
            plan_type="周卡",
        )
        m_west = Member(
            phone="13800000022",
            name="西用户",
            balance=2,
            is_active=True,
            plan_type="周卡",
        )
        db.add_all([m_east, m_west])
        db.flush()
        db.add_all(
            [
                MemberAddress(
                    member_id=m_east.id,
                    contact_name="东",
                    contact_phone="13800000011",
                    area="东区",
                    detail_address="东里1号",
                    is_default=True,
                ),
                MemberAddress(
                    member_id=m_west.id,
                    contact_name="西",
                    contact_phone="13800000022",
                    area="西区",
                    detail_address="西里2号",
                    is_default=True,
                ),
            ]
        )
        db.commit()

    r = client.post("/api/courier/login-phone", json={"phone": "13900000007"})
    assert r.status_code == 200
    courier_token = r.json()["data"]["access_token"]
    ch = {"Authorization": f"Bearer {courier_token}"}

    r = client.get(f"/api/courier/tasks?date={d.isoformat()}", headers=ch)
    assert r.status_code == 200
    payload = r.json()["data"]
    assert payload["assigned_areas"] == ["西区"]
    items = [it for g in payload["groups"] for it in g["items"]]
    assert len(items) == 1
    assert items[0]["name"] == "西用户"
    assert items[0]["area"] == "西区"
    assert items[0]["is_delivered"] is False

    r = client.get(f"/api/courier/tasks?date={d.isoformat()}&area=东区", headers=ch)
    assert r.status_code == 403
