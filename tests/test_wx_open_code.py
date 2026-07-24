"""微信开放平台 · 代码 commit / 体验码 / ext 组装。"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.shared.wx_open_code_service import (
    build_ext_json_for_tenant,
    commit_template_to_tenant,
    fetch_trial_qrcode_base64,
    get_publish_admin_state,
    list_code_templates,
    load_publish_blob,
    save_publish_blob,
)


def test_build_ext_json_rejects_without_authorizer():
    """无 authorizer 时禁止 commit，保护 OK饭等直连小程序。"""
    db = MagicMock()
    tenant = MagicMock()
    tenant.code = "t_ok"
    tenant.name = "OK饭"
    db.get.return_value = tenant
    with patch(
        "app.services.shared.wx_open_code_service.tenant_has_authorizer_tokens",
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            build_ext_json_for_tenant(db, 1)
    assert exc.value.status_code == 400
    assert "Authorizer" in str(exc.value.detail)


def test_build_ext_json_requires_tenant_code():
    db = MagicMock()
    tenant = MagicMock()
    tenant.code = ""
    tenant.name = "测试"
    db.get.return_value = tenant
    with patch(
        "app.services.shared.wx_open_code_service.tenant_has_authorizer_tokens",
        return_value=True,
    ):
        with pytest.raises(HTTPException) as exc:
            build_ext_json_for_tenant(db, 3)
    assert "tenantId" in str(exc.value.detail)


@patch("app.services.shared.wx_open_code_service.get_settings")
@patch("app.services.shared.wx_open_code_service.load_saas_blob")
@patch("app.services.shared.wx_open_code_service.get_tenant_integration_row")
@patch("app.services.shared.wx_open_code_service.tenant_has_authorizer_tokens", return_value=True)
def test_build_ext_json_ok(mock_has_auth, mock_get_row, mock_saas, mock_settings):
    db = MagicMock()
    tenant = MagicMock()
    tenant.code = "t_hello_qc"
    tenant.name = "Hello轻厨"
    db.get.return_value = tenant

    row = MagicMock()
    row.wx_mini_appid = "wx6131d6d74a3edc6f"
    row.wx_subscribe_delivery_tmpl_id = ""
    mock_get_row.return_value = row
    mock_saas.return_value = {
        "appName": "Hello轻厨",
        "defaultStoreId": 2,
        "homeTemplate": "catalog",
        "homeLayoutPreset": "standard-catalog",
        "theme": {"primaryColor": "#112233"},
        "features": {"coupon": False},
    }
    mock_settings.return_value.public_base_for_assets = "https://ok.sourcefire.cn"

    ext = build_ext_json_for_tenant(db, 3)
    assert ext["extAppid"] == "wx6131d6d74a3edc6f"
    assert ext["requiredPrivateInfos"] == ["getLocation", "chooseLocation"]
    assert ext["ext"]["tenantId"] == "t_hello_qc"
    assert ext["ext"]["storagePrefix"] == "t_hello_qc_"
    assert ext["ext"]["apiBase"] == "https://ok.sourcefire.cn"
    assert ext["ext"]["defaultStoreId"] == 2
    assert ext["ext"]["homeTemplate"] == "catalog"
    assert ext["window"]["navigationBarTitleText"] == "Hello轻厨"


@patch("app.services.shared.wx_open_code_service.save_publish_blob")
@patch("app.services.shared.wx_open_code_service.get_publish_admin_state")
@patch("app.services.shared.wx_open_code_service.get_valid_authorizer_access_token", return_value="at")
@patch("app.services.shared.wx_open_code_service.build_ext_json_for_tenant")
@patch("app.services.shared.wx_open_code_service.httpx.Client")
def test_commit_template_success(mock_client_cls, mock_build, mock_token, mock_state, mock_save):
    mock_build.return_value = {
        "extAppid": "wxabc",
        "ext": {"tenantId": "t_x"},
        "window": {},
        "requiredPrivateInfos": ["getLocation", "chooseLocation"],
    }
    mock_state.return_value = {"tenant_id": 3, "last_user_version": "1.0.0"}

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"errcode": 0, "errmsg": "ok"}
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.return_value = resp
    mock_client_cls.return_value = client

    db = MagicMock()
    out = commit_template_to_tenant(
        db, 3, template_id=1, user_version="1.0.0", user_desc="初版"
    )
    assert out["last_user_version"] == "1.0.0"
    mock_save.assert_called()
    saved = mock_save.call_args[0][2]
    assert saved["template_id"] == 1
    assert saved["last_error"] is None


@patch("app.services.shared.wx_open_code_service.get_valid_authorizer_access_token", return_value="at")
@patch("app.services.shared.wx_open_code_service.tenant_has_authorizer_tokens", return_value=True)
@patch("app.services.shared.wx_open_code_service.httpx.Client")
def test_fetch_trial_qrcode_base64(mock_client_cls, _has, _token):
    jpeg = b"\xff\xd8\xfffakejpeg"
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {"content-type": "image/jpeg"}
    resp.content = jpeg
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get.return_value = resp
    mock_client_cls.return_value = client

    out = fetch_trial_qrcode_base64(MagicMock(), 3)
    assert out["content_type"] == "image/jpeg"
    assert out["image_base64"] == base64.b64encode(jpeg).decode("ascii")


@patch("app.integrations.wechat_open_platform.get_component_access_token", return_value="ct")
@patch("app.integrations.wechat_open_platform.wechat_open_platform_configured", return_value=True)
@patch("app.services.shared.wx_open_code_service.httpx.Client")
def test_list_code_templates(mock_client_cls, _cfg, _token):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "errcode": 0,
        "template_list": [
            {"template_id": 1, "user_version": "1.0.0", "user_desc": "saas", "template_type": 0},
        ],
    }
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get.return_value = resp
    mock_client_cls.return_value = client

    items = list_code_templates(MagicMock(), template_type=0)
    assert len(items) == 1
    assert items[0]["template_id"] == 1


def test_save_and_load_publish_blob_roundtrip_shape():
    """落库结构校验（mock integration row）。"""
    row = MagicMock()
    row.extra_json = json.dumps({"saas": {"appName": "x"}})
    db = MagicMock()
    with patch(
        "app.services.shared.wx_open_code_service.get_tenant_integration_row",
        return_value=row,
    ):
        save_publish_blob(
            db,
            3,
            {"template_id": 1, "user_version": "1.0.0", "committed_at": "t", "last_error": None},
        )
        root = json.loads(row.extra_json)
        assert root["saas"]["appName"] == "x"
        assert root["wx_code_publish"]["template_id"] == 1

    with patch(
        "app.services.shared.wx_open_code_service.get_tenant_integration_row",
        return_value=row,
    ):
        blob = load_publish_blob(db, 3)
        assert blob["user_version"] == "1.0.0"


@patch("app.services.shared.wx_open_code_service.get_authorizer_admin_state")
@patch("app.services.shared.wx_open_code_service.load_publish_blob", return_value={})
@patch(
    "app.services.shared.wx_open_code_service.build_ext_json_for_tenant",
    side_effect=HTTPException(status_code=400, detail="缺 code"),
)
def test_get_publish_admin_state_with_preview_error(_build, _blob, mock_auth):
    mock_auth.return_value = {
        "authorizer_mode_active": False,
        "authorizer_appid": None,
        "component_ticket_present": True,
        "component_platform_configured": True,
    }
    out = get_publish_admin_state(MagicMock(), 1)
    assert out["default_template_id"] == 1
    assert out["ext_preview"] is None
    assert "缺 code" in (out["ext_preview_error"] or "")
