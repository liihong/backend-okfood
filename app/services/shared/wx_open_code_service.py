"""微信开放平台 · 小程序代码管理（模板列表 / commit 体验版 / 体验二维码）。

仅作用于已代授权租户（authorizer refresh_token 已落库）。
未授权租户（含 OK饭主站直连 AppID/Secret）不会走本模块，登录与支付回退逻辑不变。
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import beijing_now_naive
from app.integrations.wechat_mini import WeChatMiniError
from app.models.tenant import Tenant
from app.services.client.tenant_saas_service import (
    DEFAULT_FEATURES,
    DEFAULT_THEME,
    load_saas_blob,
)
from app.services.shared.tenant_integration_service import get_tenant_integration_row
from app.services.shared.wx_open_authorizer_service import (
    get_authorizer_admin_state,
    get_valid_authorizer_access_token,
    tenant_has_authorizer_tokens,
)

logger = logging.getLogger(__name__)

# 微信开放平台 · 代码模板 / 体验版接口
TEMPLATE_LIST_URL = "https://api.weixin.qq.com/wxa/gettemplatelist"
COMMIT_URL = "https://api.weixin.qq.com/wxa/commit"
TRIAL_QRCODE_URL = "https://api.weixin.qq.com/wxa/get_qrcode"

# extra_json 内发布状态键（与 saas / douyin 并列，互不覆盖）
PUBLISH_BLOB_KEY = "wx_code_publish"

# 普通模板库 commit 必带隐私接口声明（缺省易报 61040）
REQUIRED_PRIVATE_INFOS = ["getLocation", "chooseLocation"]


def _s(raw: Any) -> str:
    return str(raw or "").strip()


def _parse_extra_root(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        obj = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def load_publish_blob(db: Session, tenant_id: int) -> dict[str, Any]:
    """读取租户最近一次代码发布摘要（不回显敏感信息）。"""
    row = get_tenant_integration_row(db, int(tenant_id))
    root = _parse_extra_root(row.extra_json if row else None)
    blob = root.get(PUBLISH_BLOB_KEY)
    return dict(blob) if isinstance(blob, dict) else {}


def save_publish_blob(db: Session, tenant_id: int, blob: dict[str, Any]) -> None:
    """写入/合并 wx_code_publish，保留 saas、douyin 等其它键。"""
    from app.models.tenant_integration_settings import TenantIntegrationSettings

    row = get_tenant_integration_row(db, int(tenant_id))
    if row is None:
        row = TenantIntegrationSettings(tenant_id=int(tenant_id))
        db.add(row)
        db.flush()
    root = _parse_extra_root(row.extra_json)
    root[PUBLISH_BLOB_KEY] = blob
    row.extra_json = json.dumps(root, ensure_ascii=False)
    db.commit()
    db.refresh(row)


def _raise_wechat(data: dict[str, Any], *, fallback: str) -> None:
    """将微信 errcode 转为 HTTPException。"""
    errcode = data.get("errcode")
    if errcode in (None, 0):
        return
    msg = _s(data.get("errmsg")) or fallback
    # 常见业务错误用 400，凭证类用 503
    status = 503 if int(errcode or 0) in (40001, 40014, 42001) else 400
    raise HTTPException(status_code=status, detail=f"微信接口错误({errcode}): {msg}")


def list_code_templates(db: Session, *, template_type: int | None = 0) -> list[dict[str, Any]]:
    """
    拉取第三方平台代码模板库列表。

    template_type: 0=普通模板（默认），1=标准模板，None=全部。
    """
    from app.integrations.wechat_open_platform import get_component_access_token, wechat_open_platform_configured

    if not wechat_open_platform_configured():
        raise HTTPException(status_code=503, detail="微信第三方平台未配置")

    token = get_component_access_token(db)
    params: dict[str, Any] = {"access_token": token}
    if template_type is not None:
        params["template_type"] = int(template_type)

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(TEMPLATE_LIST_URL, params=params)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("gettemplatelist 请求失败")
        raise HTTPException(status_code=502, detail="拉取模板列表失败") from e

    _raise_wechat(data, fallback="拉取模板列表失败")
    items = data.get("template_list") or []
    if not isinstance(items, list):
        return []

    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        tid = it.get("template_id")
        if tid is None:
            continue
        out.append(
            {
                "template_id": int(tid),
                "user_version": _s(it.get("user_version")) or None,
                "user_desc": _s(it.get("user_desc")) or None,
                "create_time": it.get("create_time"),
                "template_type": it.get("template_type"),
                "source_miniprogram_appid": _s(it.get("source_miniprogram_appid")) or None,
                "source_miniprogram": _s(it.get("source_miniprogram")) or None,
            }
        )
    # 按 template_id 升序，便于运营选中 ID=1
    out.sort(key=lambda x: int(x["template_id"]))
    return out


def _resolve_api_base() -> str:
    """commit 注入的 apiBase：优先 BASE_URL / PUBLIC_BASE_URL。"""
    base = _s(get_settings().public_base_for_assets)
    if not base:
        raise HTTPException(
            status_code=503,
            detail="请先在 .env 配置 BASE_URL（对外 HTTPS 根地址），用于小程序 apiBase",
        )
    return base.rstrip("/")


def build_ext_json_for_tenant(db: Session, tenant_id: int) -> dict[str, Any]:
    """
    按租户 SaaS 配置组装 commit 用的 ext_json 对象（尚未 dumps）。

    未授权 / 缺 code / 缺 AppID 时抛 400，避免误把错误包推到小程序。
    """
    tenant = db.get(Tenant, int(tenant_id))
    if tenant is None:
        raise HTTPException(status_code=404, detail="租户不存在")

    # 关键：无代授权则禁止 commit，OK饭等直连租户不受影响
    if not tenant_has_authorizer_tokens(db, int(tenant_id)):
        raise HTTPException(
            status_code=400,
            detail="该租户未启用 Authorizer（无 refresh_token）。OK饭等直连小程序请继续用开发者工具上传，勿走代发布。",
        )

    code = _s(getattr(tenant, "code", None))
    if not code:
        raise HTTPException(
            status_code=400,
            detail="请先在「品牌与首页」配置外部 tenantId（tenants.code），须与小程序 X-Tenant-Id 一致",
        )

    row = get_tenant_integration_row(db, int(tenant_id))
    appid = _s(row.wx_mini_appid if row else None)
    if not appid:
        raise HTTPException(status_code=400, detail="缺少授权方 AppID，请先完成代授权")

    saas = load_saas_blob(db, int(tenant_id))
    app_name = _s(saas.get("appName")) or _s(tenant.name) or "餐饮小程序"

    default_store_raw = saas.get("defaultStoreId")
    try:
        default_store_id = max(1, int(default_store_raw)) if default_store_raw is not None else 1
    except (TypeError, ValueError):
        default_store_id = 1

    theme = dict(DEFAULT_THEME)
    if isinstance(saas.get("theme"), dict):
        theme.update({k: v for k, v in saas["theme"].items() if v is not None})

    features = dict(DEFAULT_FEATURES)
    if isinstance(saas.get("features"), dict):
        for k, v in saas["features"].items():
            if isinstance(v, bool):
                features[k] = v

    share = saas.get("share") if isinstance(saas.get("share"), dict) else {}
    legal = saas.get("legal") if isinstance(saas.get("legal"), dict) else {}
    subscribe_saas = saas.get("subscribe") if isinstance(saas.get("subscribe"), dict) else {}
    delivery_tmpl = _s(row.wx_subscribe_delivery_tmpl_id if row else None) or _s(
        subscribe_saas.get("deliveryTmplId")
    )

    storage_prefix = code if code.endswith("_") else f"{code}_"
    api_base = _resolve_api_base()

    ext_body: dict[str, Any] = {
        "tenantId": code,
        "appName": app_name,
        "storagePrefix": storage_prefix,
        "apiBase": api_base,
        "defaultStoreId": default_store_id,
        "homeTemplate": _s(saas.get("homeTemplate")) or "default",
        "homeLayoutPreset": _s(saas.get("homeLayoutPreset")) or "standard-default",
        "theme": theme,
        "features": features,
    }
    if share:
        ext_body["share"] = {k: _s(v) for k, v in share.items() if _s(v)}
    if legal:
        ext_body["legal"] = {k: _s(v) for k, v in legal.items()}
    if delivery_tmpl:
        ext_body["subscribe"] = {"deliveryTmplId": delivery_tmpl}

    return {
        "extAppid": appid,
        "ext": ext_body,
        "window": {"navigationBarTitleText": app_name},
        "requiredPrivateInfos": list(REQUIRED_PRIVATE_INFOS),
    }


def get_publish_admin_state(db: Session, tenant_id: int) -> dict[str, Any]:
    """管理端：发布状态 + 将注入的 ext 摘要 + authorizer 是否就绪。"""
    auth = get_authorizer_admin_state(db, int(tenant_id))
    blob = load_publish_blob(db, int(tenant_id))
    ext_preview: dict[str, Any] | None = None
    ext_error: str | None = None
    try:
        ext_obj = build_ext_json_for_tenant(db, int(tenant_id))
        ext = ext_obj.get("ext") if isinstance(ext_obj.get("ext"), dict) else {}
        ext_preview = {
            "extAppid": ext_obj.get("extAppid"),
            "tenantId": ext.get("tenantId"),
            "appName": ext.get("appName"),
            "apiBase": ext.get("apiBase"),
            "defaultStoreId": ext.get("defaultStoreId"),
            "homeTemplate": ext.get("homeTemplate"),
            "homeLayoutPreset": ext.get("homeLayoutPreset"),
            "storagePrefix": ext.get("storagePrefix"),
        }
    except HTTPException as e:
        ext_error = str(e.detail)

    return {
        "tenant_id": int(tenant_id),
        "authorizer_mode_active": bool(auth.get("authorizer_mode_active")),
        "authorizer_appid": auth.get("authorizer_appid"),
        "component_ticket_present": bool(auth.get("component_ticket_present")),
        "component_platform_configured": bool(auth.get("component_platform_configured")),
        "last_template_id": blob.get("template_id"),
        "last_user_version": blob.get("user_version"),
        "last_user_desc": blob.get("user_desc"),
        "last_committed_at": blob.get("committed_at"),
        "last_error": blob.get("last_error"),
        "ext_preview": ext_preview,
        "ext_preview_error": ext_error,
        "default_template_id": 1,
    }


def commit_template_to_tenant(
    db: Session,
    tenant_id: int,
    *,
    template_id: int,
    user_version: str,
    user_desc: str,
) -> dict[str, Any]:
    """
    将模板库代码 commit 到已授权小程序并生成体验版。

    成功后写入 wx_code_publish；失败写入 last_error（不清空历史版本号）。
    """
    tid = int(template_id)
    if tid < 0:
        raise HTTPException(status_code=400, detail="template_id 无效")

    version = _s(user_version)
    desc = _s(user_desc)
    if not version:
        raise HTTPException(status_code=400, detail="user_version 不能为空")
    if len(version) > 64:
        raise HTTPException(status_code=400, detail="user_version 不能超过 64 字符")
    if not desc:
        raise HTTPException(status_code=400, detail="user_desc 不能为空")

    ext_obj = build_ext_json_for_tenant(db, int(tenant_id))
    ext_json_str = json.dumps(ext_obj, ensure_ascii=False, separators=(",", ":"))

    try:
        access_token = get_valid_authorizer_access_token(db, int(tenant_id))
    except WeChatMiniError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    payload = {
        "template_id": tid,
        "ext_json": ext_json_str,
        "user_version": version,
        "user_desc": desc,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(COMMIT_URL, params={"access_token": access_token}, json=payload)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("wxa/commit 请求失败 tenant_id=%s", tenant_id)
        err_blob = load_publish_blob(db, int(tenant_id))
        err_blob["last_error"] = "commit 网络失败"
        save_publish_blob(db, int(tenant_id), err_blob)
        raise HTTPException(status_code=502, detail="上传体验版失败（网络）") from e

    errcode = data.get("errcode")
    if errcode not in (None, 0):
        msg = _s(data.get("errmsg")) or "commit 失败"
        err_blob = load_publish_blob(db, int(tenant_id))
        err_blob["last_error"] = f"{errcode}: {msg}"
        save_publish_blob(db, int(tenant_id), err_blob)
        _raise_wechat(data, fallback="commit 失败")

    now = beijing_now_naive().isoformat(timespec="seconds")
    save_publish_blob(
        db,
        int(tenant_id),
        {
            "template_id": tid,
            "user_version": version,
            "user_desc": desc,
            "committed_at": now,
            "last_error": None,
        },
    )
    logger.info(
        "wxa/commit 成功 tenant_id=%s template_id=%s version=%s",
        tenant_id,
        tid,
        version,
    )
    state = get_publish_admin_state(db, int(tenant_id))
    state["ext_json_chars"] = len(ext_json_str)
    return state


def fetch_trial_qrcode_base64(
    db: Session,
    tenant_id: int,
    *,
    path: str | None = None,
) -> dict[str, Any]:
    """
    拉取体验版二维码，返回 base64（供管理端 <img> 展示）。

    未授权租户直接 400，避免误调到 OK饭直连凭证。
    """
    if not tenant_has_authorizer_tokens(db, int(tenant_id)):
        raise HTTPException(
            status_code=400,
            detail="该租户未启用 Authorizer，无法拉取代开发体验码",
        )

    try:
        access_token = get_valid_authorizer_access_token(db, int(tenant_id))
    except WeChatMiniError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    params: dict[str, str] = {"access_token": access_token}
    page_path = _s(path)
    if page_path:
        # 微信要求 path 做一次 urlencode
        params["path"] = quote(page_path, safe="")

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(TRIAL_QRCODE_URL, params=params)
            r.raise_for_status()
            content_type = (r.headers.get("content-type") or "").lower()
            body = r.content
    except httpx.HTTPError as e:
        logger.exception("get_qrcode 请求失败 tenant_id=%s", tenant_id)
        raise HTTPException(status_code=502, detail="拉取体验码失败（网络）") from e

    # 错误时微信返回 JSON
    if "application/json" in content_type or (body[:1] == b"{"):
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=502, detail="体验码响应无法解析") from e
        if isinstance(data, dict):
            _raise_wechat(data, fallback="拉取体验码失败")
        raise HTTPException(status_code=502, detail="拉取体验码失败")

    b64 = base64.b64encode(body).decode("ascii")
    ct = "image/jpeg"
    if "png" in content_type:
        ct = "image/png"
    return {
        "content_type": ct,
        "image_base64": b64,
        "byte_length": len(body),
        "path": page_path or None,
    }
