"""SaaS 多租户解析与配置（不影响 OK饭 仅 X-Store-Id 路径）。"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.tenant_resolve import (
    lookup_tenant_id_by_wx_appid,
    resolve_public_tenant_store,
    resolve_tenant_id_from_header_value,
)
from app.services.client.tenant_saas_service import (
    HOME_LAYOUT_PRESETS,
    build_home_layout_public,
    build_tenant_config_public,
    merge_saas_patch,
)


@dataclass
class _FakeStore:
    id: int
    tenant_id: int
    is_active: bool = True


@dataclass
class _FakeTenant:
    id: int
    name: str
    code: str | None = None
    is_active: bool = True


def test_resolve_tenant_id_numeric_and_code():
    db = MagicMock()
    tenant = _FakeTenant(id=2, name="品牌B", code="t_brand_b")

    def _get(model, pk):
        if pk == 2:
            return tenant
        return None

    db.get.side_effect = _get
    assert resolve_tenant_id_from_header_value(db, "2") == 2

    db.scalar.return_value = tenant
    assert resolve_tenant_id_from_header_value(db, "t_brand_b") == 2


def test_lookup_tenant_by_wx_appid_global_fallback(monkeypatch):
    db = MagicMock()
    db.scalar.return_value = None
    monkeypatch.setenv("WX_MINI_APPID", "wx_okfood_main")
    monkeypatch.setenv("DEFAULT_TENANT_ID", "1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    tid = lookup_tenant_id_by_wx_appid(db, "wx_okfood_main")
    get_settings.cache_clear()
    assert tid == 1


def test_resolve_public_store_okfood_path_no_tenant_header():
    """OK饭：无 X-Tenant-Id，仅默认门店 1，行为与改造前一致。"""
    db = MagicMock()

    def _get(model, pk):
        name = getattr(model, "__name__", "")
        if name == "Store" and pk == 1:
            return _FakeStore(id=1, tenant_id=1)
        if name == "Tenant" and pk == 1:
            return _FakeTenant(id=1, name="OK饭")
        return None

    db.get.side_effect = _get

    class _Req:
        headers = {}

    ctx = resolve_public_tenant_store(db, _Req())
    assert ctx.store_id == 1
    assert ctx.tenant_id == 1


def test_resolve_public_store_rejects_tenant_store_mismatch():
    db = MagicMock()

    def _get(model, pk):
        name = getattr(model, "__name__", "")
        if name == "Store" and pk == 1:
            return _FakeStore(id=1, tenant_id=1)
        if name == "Tenant" and pk == 2:
            return _FakeTenant(id=2, name="其它", code="t_other")
        if name == "Tenant" and pk == 1:
            return _FakeTenant(id=1, name="OK饭")
        return None

    db.get.side_effect = _get
    db.scalar.return_value = _FakeTenant(id=2, name="其它", code="t_other")

    class _Req:
        headers = {"X-Tenant-Id": "t_other", "X-Store-Id": "1"}

    with pytest.raises(HTTPException) as exc:
        resolve_public_tenant_store(db, _Req())
    assert exc.value.status_code == 403


def test_merge_saas_patch_nested():
    base = {"theme": {"primaryColor": "#111"}, "features": {"coupon": True}}
    out = merge_saas_patch(base, {"theme": {"pageBg": "#fff"}, "appName": "测试"})
    assert out["theme"]["primaryColor"] == "#111"
    assert out["theme"]["pageBg"] == "#fff"
    assert out["appName"] == "测试"


def test_build_tenant_config_public_minimal():
    db = MagicMock()
    tenant = _FakeTenant(id=1, name="OK饭", code=None)

    def _get(model, pk):
        name = getattr(model, "__name__", "")
        if name == "Tenant":
            return tenant
        return None

    db.get.side_effect = _get

    from app.core.store_scope import PublicStoreContext

    ctx = PublicStoreContext(store_id=1, tenant_id=1, tenant_code=None)
    cfg = build_tenant_config_public(db, ctx)
    assert cfg is not None
    assert cfg["tenantId"] == "1"
    assert cfg["appName"] == "OK饭"
    assert cfg["features"]["courierMode"] is True


def test_build_home_layout_uses_preset():
    db = MagicMock()

    def _get(model, pk):
        name = getattr(model, "__name__", "")
        if name == "Tenant":
            return _FakeTenant(id=1, name="OK饭")
        return None

    db.get.side_effect = _get

    from app.core.store_scope import PublicStoreContext

    ctx = PublicStoreContext(store_id=1, tenant_id=1)
    layout = build_home_layout_public(db, ctx)
    assert layout["template"] == "default"
    assert len(layout["blocks"]) == len(HOME_LAYOUT_PRESETS["standard-default"]["blocks"])
