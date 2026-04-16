"""管理端图片上传：需管理员 JWT。"""

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
def admin_client_with_db(tmp_path):
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
    yield client, tmp_path
    app.dependency_overrides.pop(get_db, None)


def test_admin_upload_requires_auth(admin_client_with_db):
    client, _ = admin_client_with_db
    files = {"file": ("x.png", b"x", "image/png")}
    r = client.post("/api/admin/upload", files=files)
    assert r.status_code == 401


def test_admin_upload_success(admin_client_with_db, monkeypatch):
    from app.core.config import settings

    client, tmp_path = admin_client_with_db
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "BASE_URL", "")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "")

    login = client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]

    files = {"file": ("x.png", b"\x89PNG\r\n\x1a\n\x00\x00", "image/png")}
    r = client.post(
        "/api/admin/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 200
    url = body["data"]["url"]
    assert url.startswith("/static/uploads/images/")
    assert url.endswith(".png")


def test_admin_upload_with_base_url(admin_client_with_db, monkeypatch):
    from app.core.config import settings

    client, tmp_path = admin_client_with_db
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "BASE_URL", "https://api.example.com")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "")

    login = client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    token = login.json()["data"]["access_token"]
    files = {"file": ("x.png", b"x", "image/png")}
    r = client.post(
        "/api/admin/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert r.status_code == 200
    url = r.json()["data"]["url"]
    assert url.startswith("https://api.example.com/static/uploads/images/")
