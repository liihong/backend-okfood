"""管理端配送大表：聚合、默认地址、请假过滤。"""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.admin_user import AdminUser
from app.models.delivery_region import DeliveryRegion
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


def _token(client: TestClient) -> str:
    r = client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return r.json()["data"]["access_token"]


def test_delivery_sheet_aggregates_same_address(admin_full_client):
    client, SessionLocal = admin_full_client
    d = date(2026, 4, 20)
    with SessionLocal() as db:
        m1 = Member(
            phone="13800000001",
            name="Jia",
            balance=2,
            is_active=True,
            plan_type="周卡",
        )
        m2 = Member(
            phone="13800000002",
            name="Yi",
            balance=1,
            is_active=True,
            plan_type="周卡",
        )
        db.add_all([m1, m2])
        db.flush()
        db.add_all(
            [
                MemberAddress(
                    member_id=m1.id,
                    contact_name="Jia",
                    contact_phone="13800000001",
                    area="东区",
                    detail_address="花园1号",
                    is_default=True,
                ),
                MemberAddress(
                    member_id=m2.id,
                    contact_name="Yi",
                    contact_phone="13800000002",
                    area="东区",
                    detail_address="花园1号",
                    is_default=True,
                ),
            ]
        )
        db.commit()

    token = _token(client)
    r = client.get(f"/api/admin/delivery-sheet?delivery_date={d.isoformat()}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 200
    data = body["data"]
    assert data["delivery_date"] == d.isoformat()
    assert len(data["groups"]) == 1
    g0 = data["groups"][0]
    assert g0["area"] == "东区"
    assert g0["stop_count"] == 1
    assert g0["meal_total"] == 2
    assert len(g0["stops"]) == 1
    st = g0["stops"][0]
    assert st["meal_count"] == 2
    assert len(st["members"]) == 2
    assert data.get("active_regions") == []


def test_delivery_sheet_flags_unassigned_area(admin_full_client):
    client, SessionLocal = admin_full_client
    d = date(2026, 4, 21)
    with SessionLocal() as db:
        db.add(
            Member(
                phone="13600000001",
                name="NoArea",
                balance=1,
                is_active=True,
                plan_type="周卡",
            )
        )
        db.commit()

    token = _token(client)
    r = client.get(f"/api/admin/delivery-sheet?delivery_date={d.isoformat()}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["groups"]) == 1
    st0 = data["groups"][0]["stops"][0]
    assert st0["has_area_issue"] is True
    assert data["groups"][0]["has_area_issue"] is True
    assert st0["members"][0]["area_issue"] is True


def test_delivery_sheet_flags_unknown_area_when_regions_exist(admin_full_client):
    client, SessionLocal = admin_full_client
    d = date(2026, 4, 22)
    with SessionLocal() as db:
        db.add(
            DeliveryRegion(
                id=1,
                name="东区",
                code=None,
                polygon_json=[[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                priority=0,
                is_active=True,
            )
        )
        mem = Member(
            phone="13600000002",
            name="Bad",
            balance=1,
            is_active=True,
            plan_type="周卡",
        )
        db.add(mem)
        db.flush()
        db.add(
            MemberAddress(
                member_id=mem.id,
                contact_name="Bad",
                contact_phone="13600000002",
                area="不存在的区",
                detail_address="某路2号",
                is_default=True,
            )
        )
        db.commit()

    token = _token(client)
    r = client.get(f"/api/admin/delivery-sheet?delivery_date={d.isoformat()}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert "东区" in data["active_regions"]
    st0 = data["groups"][0]["stops"][0]
    assert st0["has_area_issue"] is True


def test_delivery_sheet_excludes_leave_range(admin_full_client):
    client, SessionLocal = admin_full_client
    d = date(2026, 5, 10)
    with SessionLocal() as db:
        db.add(
            Member(
                phone="13900000001",
                name="请假用户",
                balance=5,
                is_active=True,
                plan_type="月卡",
                leave_range_start=date(2026, 5, 1),
                leave_range_end=date(2026, 5, 15),
            )
        )
        db.commit()

    token = _token(client)
    r = client.get(f"/api/admin/delivery-sheet?delivery_date={d.isoformat()}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["groups"] == []


@patch("app.services.courier_service.today_shanghai", return_value=date(2026, 5, 9))
def test_delivery_sheet_excludes_tomorrow_leave_flag(_mock_today, admin_full_client):
    """is_leaved_tomorrow 仅剔除「业务今天+1」对应的配送日，不影响当日大表。"""
    client, SessionLocal = admin_full_client
    tomorrow = date(2026, 5, 10)
    today = date(2026, 5, 9)
    with SessionLocal() as db:
        m = Member(
            phone="13900000002",
            name="明天请假",
            balance=3,
            is_active=True,
            plan_type="周卡",
            is_leaved_tomorrow=True,
        )
        db.add(m)
        db.flush()
        db.add(
            MemberAddress(
                member_id=m.id,
                contact_name="明天请假",
                contact_phone="13900000002",
                area="东区",
                detail_address="测试路1号",
                is_default=True,
            )
        )
        db.commit()

    token = _token(client)
    r_today = client.get(
        f"/api/admin/delivery-sheet?delivery_date={today.isoformat()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_today.status_code == 200
    d0 = r_today.json()["data"]
    meal_today = sum(g["meal_total"] for g in d0.get("groups") or [])
    assert meal_today >= 1

    r_tomorrow = client.get(
        f"/api/admin/delivery-sheet?delivery_date={tomorrow.isoformat()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_tomorrow.status_code == 200
    assert r_tomorrow.json()["data"]["groups"] == []


def test_delivery_sheet_area_filter(admin_full_client):
    client, SessionLocal = admin_full_client
    d = date(2026, 6, 1)
    with SessionLocal() as db:
        east = Member(
            phone="13700000001",
            name="东",
            balance=1,
            is_active=True,
            plan_type="周卡",
        )
        west = Member(
            phone="13700000002",
            name="西",
            balance=1,
            is_active=True,
            plan_type="周卡",
        )
        db.add_all([east, west])
        db.flush()
        db.add_all(
            [
                MemberAddress(
                    member_id=east.id,
                    contact_name="东",
                    contact_phone="13700000001",
                    area="东区",
                    detail_address="东1",
                    is_default=True,
                ),
                MemberAddress(
                    member_id=west.id,
                    contact_name="西",
                    contact_phone="13700000002",
                    area="西区",
                    detail_address="西1",
                    is_default=True,
                ),
            ]
        )
        db.commit()

    token = _token(client)
    r = client.get(
        f"/api/admin/delivery-sheet?delivery_date={d.isoformat()}&area=东区",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["groups"]) == 1
    assert data["groups"][0]["area"] == "东区"
    assert data["groups"][0]["meal_total"] == 1
