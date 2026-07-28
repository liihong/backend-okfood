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

# 微信开放平台 · 代码模板 / 体验版 / 审核发布接口
TEMPLATE_LIST_URL = "https://api.weixin.qq.com/wxa/gettemplatelist"
COMMIT_URL = "https://api.weixin.qq.com/wxa/commit"
TRIAL_QRCODE_URL = "https://api.weixin.qq.com/wxa/get_qrcode"
GET_CATEGORY_URL = "https://api.weixin.qq.com/wxa/get_category"
SUBMIT_AUDIT_URL = "https://api.weixin.qq.com/wxa/submit_audit"
AUDIT_STATUS_URL = "https://api.weixin.qq.com/wxa/get_latest_auditstatus"
RELEASE_URL = "https://api.weixin.qq.com/wxa/release"

# 微信 get_latest_auditstatus.status 文案（管理端展示）
AUDIT_STATUS_LABELS: dict[int, str] = {
    0: "审核成功",
    1: "审核被拒绝",
    2: "审核中",
    3: "已撤回",
    4: "审核延后",
}

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


def _patch_publish_blob(db: Session, tenant_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    """增量更新 wx_code_publish，避免覆盖审核/发布等历史字段。"""
    blob = load_publish_blob(db, int(tenant_id))
    blob.update(patch)
    save_publish_blob(db, int(tenant_id), blob)
    return blob


def _ensure_authorizer_for_code_ops(db: Session, tenant_id: int) -> None:
    """commit / 提审 / 发布等代开发操作的前置校验。"""
    if not tenant_has_authorizer_tokens(db, int(tenant_id)):
        raise HTTPException(
            status_code=400,
            detail="该租户未启用 Authorizer。OK饭等直连小程序请用微信开发者工具上传，勿走代发布。",
        )


def _authorizer_access_token_or_http(db: Session, tenant_id: int) -> str:
    try:
        return get_valid_authorizer_access_token(db, int(tenant_id))
    except WeChatMiniError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e


def _audit_fields_from_blob(blob: dict[str, Any]) -> dict[str, Any]:
    """从 publish blob 提取审核/正式版摘要。"""
    status_raw = blob.get("audit_status")
    try:
        audit_status = int(status_raw) if status_raw is not None else None
    except (TypeError, ValueError):
        audit_status = None
    return {
        "audit_id": blob.get("audit_id"),
        "audit_status": audit_status,
        "audit_status_label": AUDIT_STATUS_LABELS.get(audit_status) if audit_status is not None else None,
        "audit_reason": blob.get("audit_reason"),
        "audit_user_version": blob.get("audit_user_version"),
        "audit_user_desc": blob.get("audit_user_desc"),
        "audit_submitted_at": blob.get("audit_submitted_at"),
        "released_at": blob.get("released_at"),
        "can_release": audit_status == 0 and not blob.get("released_at"),
    }


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

    try:
        token = get_component_access_token(db)
    except WeChatMiniError as e:
        # 将 token 获取失败（如 IP 白名单、ticket 未就绪）转为可读 HTTP 错误，避免 500
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
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
        **_audit_fields_from_blob(blob),
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
        _patch_publish_blob(db, int(tenant_id), {"last_error": "commit 网络失败"})
        raise HTTPException(status_code=502, detail="上传体验版失败（网络）") from e

    errcode = data.get("errcode")
    if errcode not in (None, 0):
        msg = _s(data.get("errmsg")) or "commit 失败"
        _patch_publish_blob(db, int(tenant_id), {"last_error": f"{errcode}: {msg}"})
        _raise_wechat(data, fallback="commit 失败")

    now = beijing_now_naive().isoformat(timespec="seconds")
    _patch_publish_blob(
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


def list_audit_categories(db: Session, tenant_id: int) -> list[dict[str, Any]]:
    """拉取已授权小程序在微信后台配置的可选类目（提审 item_list 来源）。"""
    _ensure_authorizer_for_code_ops(db, int(tenant_id))
    token = _authorizer_access_token_or_http(db, int(tenant_id))

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(GET_CATEGORY_URL, params={"access_token": token})
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("get_category 请求失败 tenant_id=%s", tenant_id)
        raise HTTPException(status_code=502, detail="拉取小程序类目失败（网络）") from e

    _raise_wechat(data, fallback="拉取小程序类目失败")
    raw = data.get("category_list") or []
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        first_class = _s(it.get("first_class"))
        second_class = _s(it.get("second_class"))
        try:
            first_id = int(it.get("first_id"))
            second_id = int(it.get("second_id"))
        except (TypeError, ValueError):
            continue
        if not first_class or not second_class:
            continue
        tag = _s(it.get("tag")) or f"{first_class} {second_class}".strip()
        out.append(
            {
                "first_class": first_class,
                "second_class": second_class,
                "first_id": first_id,
                "second_id": second_id,
                "tag": tag,
            }
        )
    return out


def submit_code_audit(
    db: Session,
    tenant_id: int,
    *,
    item_list: list[dict[str, Any]],
    version_desc: str | None = None,
    feedback_info: str | None = None,
) -> dict[str, Any]:
    """将当前体验版代码提交微信审核（须先 commit 体验版）。"""
    _ensure_authorizer_for_code_ops(db, int(tenant_id))
    if not item_list:
        raise HTTPException(status_code=400, detail="请至少选择一个审核类目")

    items: list[dict[str, Any]] = []
    for raw in item_list[:5]:
        if not isinstance(raw, dict):
            continue
        address = _s(raw.get("address")) or "pages/home/index"
        tag = _s(raw.get("tag"))
        first_class = _s(raw.get("first_class"))
        second_class = _s(raw.get("second_class"))
        title = _s(raw.get("title")) or "首页"
        try:
            first_id = int(raw.get("first_id"))
            second_id = int(raw.get("second_id"))
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail="类目 ID 无效") from e
        if not tag or not first_class or not second_class:
            raise HTTPException(status_code=400, detail="类目信息不完整")
        items.append(
            {
                "address": address,
                "tag": tag,
                "first_class": first_class,
                "second_class": second_class,
                "first_id": first_id,
                "second_id": second_id,
                "title": title,
            }
        )
    if not items:
        raise HTTPException(status_code=400, detail="审核类目无效")

    token = _authorizer_access_token_or_http(db, int(tenant_id))
    payload: dict[str, Any] = {"item_list": items}
    desc = _s(version_desc)
    if desc:
        payload["version_desc"] = desc
    fb = _s(feedback_info)
    if fb:
        payload["feedback_info"] = fb[:200]

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(SUBMIT_AUDIT_URL, params={"access_token": token}, json=payload)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("submit_audit 请求失败 tenant_id=%s", tenant_id)
        raise HTTPException(status_code=502, detail="提交审核失败（网络）") from e

    errcode = data.get("errcode")
    if errcode not in (None, 0):
        msg = _s(data.get("errmsg")) or "提交审核失败"
        _patch_publish_blob(db, int(tenant_id), {"last_error": f"audit {errcode}: {msg}"})
        _raise_wechat(data, fallback="提交审核失败")

    audit_id = data.get("auditid")
    now = beijing_now_naive().isoformat(timespec="seconds")
    blob = load_publish_blob(db, int(tenant_id))
    _patch_publish_blob(
        db,
        int(tenant_id),
        {
            "audit_id": int(audit_id) if audit_id is not None else None,
            "audit_status": 2,
            "audit_reason": None,
            "audit_user_version": blob.get("user_version"),
            "audit_user_desc": blob.get("user_desc"),
            "audit_submitted_at": now,
            "released_at": None,
            "last_error": None,
        },
    )
    logger.info("submit_audit 成功 tenant_id=%s audit_id=%s", tenant_id, audit_id)
    return get_publish_admin_state(db, int(tenant_id))


def fetch_latest_audit_status(db: Session, tenant_id: int) -> dict[str, Any]:
    """查询最新一次提审单状态，并同步落库。"""
    _ensure_authorizer_for_code_ops(db, int(tenant_id))
    token = _authorizer_access_token_or_http(db, int(tenant_id))

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(AUDIT_STATUS_URL, params={"access_token": token})
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("get_latest_auditstatus 请求失败 tenant_id=%s", tenant_id)
        raise HTTPException(status_code=502, detail="查询审核状态失败（网络）") from e

    errcode = data.get("errcode")
    if errcode not in (None, 0):
        # 85058：从未提交过审核 — 不算异常，返回空状态
        if int(errcode or 0) == 85058:
            return get_publish_admin_state(db, int(tenant_id))
        _raise_wechat(data, fallback="查询审核状态失败")

    status_raw = data.get("status")
    try:
        status = int(status_raw) if status_raw is not None else None
    except (TypeError, ValueError):
        status = None

    patch: dict[str, Any] = {
        "audit_status": status,
        "audit_reason": _s(data.get("reason")) or None,
    }
    if data.get("auditid") is not None:
        patch["audit_id"] = int(data["auditid"])
    if _s(data.get("user_version")):
        patch["audit_user_version"] = _s(data.get("user_version"))
    if _s(data.get("user_desc")):
        patch["audit_user_desc"] = _s(data.get("user_desc"))
    _patch_publish_blob(db, int(tenant_id), patch)

    state = get_publish_admin_state(db, int(tenant_id))
    state["audit_detail"] = {
        "auditid": data.get("auditid"),
        "status": status,
        "status_label": AUDIT_STATUS_LABELS.get(status) if status is not None else None,
        "reason": _s(data.get("reason")) or None,
        "user_version": _s(data.get("user_version")) or None,
        "user_desc": _s(data.get("user_desc")) or None,
        "submit_audit_time": data.get("submit_audit_time"),
    }
    return state


def release_audited_code(db: Session, tenant_id: int) -> dict[str, Any]:
    """发布最后一个审核通过的小程序版本（全量上线）。"""
    _ensure_authorizer_for_code_ops(db, int(tenant_id))
    blob = load_publish_blob(db, int(tenant_id))
    audit_fields = _audit_fields_from_blob(blob)
    if not audit_fields.get("can_release"):
        raise HTTPException(
            status_code=400,
            detail="当前不可发布：须先完成提审且审核通过（status=0），且尚未发布",
        )

    token = _authorizer_access_token_or_http(db, int(tenant_id))
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(RELEASE_URL, params={"access_token": token}, json={})
            r.raise_for_status()
            data: dict[str, Any] = r.json()
    except httpx.HTTPError as e:
        logger.exception("wxa/release 请求失败 tenant_id=%s", tenant_id)
        raise HTTPException(status_code=502, detail="发布正式版失败（网络）") from e

    errcode = data.get("errcode")
    if errcode not in (None, 0):
        msg = _s(data.get("errmsg")) or "发布失败"
        _patch_publish_blob(db, int(tenant_id), {"last_error": f"release {errcode}: {msg}"})
        _raise_wechat(data, fallback="发布正式版失败")

    now = beijing_now_naive().isoformat(timespec="seconds")
    _patch_publish_blob(
        db,
        int(tenant_id),
        {"released_at": now, "last_error": None},
    )
    logger.info("wxa/release 成功 tenant_id=%s", tenant_id)
    return get_publish_admin_state(db, int(tenant_id))
