"""管理端登录接口：用内存 SQLite + 依赖覆盖，避免依赖本机 MySQL。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.session import get_db
from app.main import app
from app.models.admin_user import AdminUser


@pytest.fixture
def admin_login_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AdminUser.__table__.create(bind=engine)
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
    yield client
    app.dependency_overrides.pop(get_db, None)


def test_admin_login_success(admin_login_client: TestClient):
    r = admin_login_client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 200
    assert body["data"] is not None
    assert "access_token" in body["data"]
    assert body["data"].get("token_type") == "bearer"
    assert isinstance(body["msg"], str)


def test_admin_login_wrong_password(admin_login_client: TestClient):
    r = admin_login_client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == 401
    assert body["data"] is None
