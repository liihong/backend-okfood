"""SaaS 租户公开配置与首页 layout（读 extra_json.saas；404 时模板库 fallback ext）。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.store_scope import PublicStoreContext
from app.core.tenant_resolve import tenant_external_code
from app.models.tenant import Tenant
from app.services.shared.tenant_integration_service import get_tenant_integration_row

# 与 okfood-template/src/config/tenant.js DEFAULT_FEATURES 对齐
DEFAULT_FEATURES: dict[str, bool] = {
    "douyinRedeem": False,
    "courierMode": True,
    "membershipCard": True,
    "retailMenu": True,
    "leaveManagement": True,
    "coupon": True,
}

DEFAULT_THEME: dict[str, str] = {
    "primaryColor": "#73B054",
    "pageBg": "#f7f5f0",
}

# 与 okfood-template/src/utils/homeLayout.js HOME_LAYOUT_PRESETS 对齐
HOME_LAYOUT_PRESETS: dict[str, dict[str, Any]] = {
    "standard-default": {
        "template": "default",
        "blocks": [
            {"type": "banner_swiper", "props": {}},
            {"type": "member_login_bar", "props": {}},
            {"type": "membership_strip", "props": {}},
            {"type": "featured_dish", "props": {"title": "今日推荐菜"}},
        ],
    },
    "standard-minimal": {
        "template": "minimal",
        "blocks": [
            {"type": "banner_swiper", "props": {}},
            {"type": "member_login_bar", "props": {}},
            {
                "type": "nav_grid",
                "props": {
                    "items": [{"label": "立即点单", "path": "/pages/order/index", "mode": "switchTab"}],
                },
            },
        ],
    },
    "standard-catalog": {
        "template": "catalog",
        "blocks": [
            {"type": "banner_swiper", "props": {}},
            {"type": "member_login_bar", "props": {}},
            {
                "type": "nav_grid",
                "props": {
                    "items": [
                        {"label": "周菜单", "path": "/pages/order/index", "mode": "switchTab"},
                        {"label": "我的订单", "path": "/pages/orders/index", "mode": "switchTab"},
                        {"label": "会员中心", "path": "/pages/mine/index", "mode": "switchTab"},
                    ],
                },
            },
            {"type": "featured_dish", "props": {"title": "今日主推"}},
        ],
    },
}


def _strip(s: Any) -> str:
    return str(s or "").strip()


def _load_extra_root(db: Session, tenant_id: int) -> dict[str, Any]:
    """读取 tenant_integration_settings.extra_json 根对象。"""
    row = get_tenant_integration_row(db, int(tenant_id))
    if row is None or not row.extra_json:
        return {}
    try:
        obj = json.loads(str(row.extra_json))
    except (TypeError, json.JSONDecodeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def load_saas_blob(db: Session, tenant_id: int) -> dict[str, Any]:
    """读取 extra_json 内 saas 配置块（平台管理可编辑）。"""
    root = _load_extra_root(db, tenant_id)
    saas = root.get("saas")
    return deepcopy(saas) if isinstance(saas, dict) else {}


def save_saas_blob(db: Session, tenant_id: int, saas: dict[str, Any]) -> None:
    """合并写入 extra_json.saas（保留 douyin 等其它键）。"""
    from app.models.tenant_integration_settings import TenantIntegrationSettings

    row = get_tenant_integration_row(db, int(tenant_id))
    if row is None:
        row = TenantIntegrationSettings(tenant_id=int(tenant_id))
        db.add(row)
    root = _load_extra_root(db, tenant_id)
    root["saas"] = saas
    row.extra_json = json.dumps(root, ensure_ascii=False)
    db.commit()
    db.refresh(row)


def merge_saas_patch(existing: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """浅合并 patch 到 saas 配置（嵌套 dict 做一层 merge）。"""
    out = deepcopy(existing)
    for key, val in patch.items():
        if val is None:
            out.pop(key, None)
            continue
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            merged = dict(out[key])
            merged.update(val)
            out[key] = merged
        else:
            out[key] = val
    return out


def build_tenant_config_public(db: Session, ctx: PublicStoreContext) -> dict[str, Any] | None:
    """
    构造 GET /api/tenant/config 的 data 载荷（camelCase，与 ext.ext / 模板库 mergeTenantServerConfig 对齐）。
    """
    tenant = db.get(Tenant, int(ctx.tenant_id))
    if tenant is None or not tenant.is_active:
        return None

    saas = load_saas_blob(db, int(ctx.tenant_id))
    integration = get_tenant_integration_row(db, int(ctx.tenant_id))

    app_name = _strip(saas.get("appName")) or _strip(tenant.name) or "餐饮小程序"
    external_id = tenant_external_code(db, int(ctx.tenant_id))

    default_store_raw = saas.get("defaultStoreId")
    if default_store_raw is not None:
        try:
            default_store_id = max(1, int(default_store_raw))
        except (TypeError, ValueError):
            default_store_id = int(ctx.store_id)
    else:
        default_store_id = int(ctx.store_id)

    theme = dict(DEFAULT_THEME)
    if isinstance(saas.get("theme"), dict):
        theme.update({k: v for k, v in saas["theme"].items() if v is not None})

    features = dict(DEFAULT_FEATURES)
    if isinstance(saas.get("features"), dict):
        for k, v in saas["features"].items():
            if isinstance(v, bool):
                features[k] = v

    subscribe_saas = saas.get("subscribe") if isinstance(saas.get("subscribe"), dict) else {}
    delivery_tmpl = _strip(integration.wx_subscribe_delivery_tmpl_id if integration else None) or _strip(
        subscribe_saas.get("deliveryTmplId")
    )

    share_defaults = {
        "homeTitle": f"{app_name} — 今日新鲜上线",
        "orderTitle": f"{app_name} — 每周新鲜菜单",
        "mineSlogan": "自律，从今天第一顿开始",
    }
    share = dict(share_defaults)
    if isinstance(saas.get("share"), dict):
        share.update({k: _strip(v) for k, v in saas["share"].items() if _strip(v)})

    legal_defaults = {
        "membershipAgreementTitle": f"{app_name}膳食卡用户服务及配送协议",
        "membershipAgreementUrl": "",
    }
    legal = dict(legal_defaults)
    if isinstance(saas.get("legal"), dict):
        legal.update({k: _strip(v) for k, v in saas["legal"].items()})

    return {
        "tenantId": external_id,
        "appName": app_name,
        "defaultStoreId": default_store_id,
        "homeTemplate": _strip(saas.get("homeTemplate")) or "default",
        "homeLayoutPreset": _strip(saas.get("homeLayoutPreset")) or "standard-default",
        "theme": theme,
        "features": features,
        "share": share,
        "legal": legal,
        "subscribe": {"deliveryTmplId": delivery_tmpl},
    }


def build_home_layout_public(db: Session, ctx: PublicStoreContext) -> dict[str, Any]:
    """
    构造 GET /api/home/layout 的 data 载荷。

    优先 extra_json.saas.homeLayout；否则按 homeLayoutPreset 返回内置 preset。
    """
    saas = load_saas_blob(db, int(ctx.tenant_id))
    preset_key = _strip(saas.get("homeLayoutPreset")) or "standard-default"
    template_override = _strip(saas.get("homeTemplate"))

    custom = saas.get("homeLayout")
    if isinstance(custom, dict) and isinstance(custom.get("blocks"), list) and custom["blocks"]:
        layout = deepcopy(custom)
        if template_override:
            layout["template"] = template_override
        elif not _strip(layout.get("template")):
            layout["template"] = "default"
        if not isinstance(layout.get("theme"), dict):
            layout["theme"] = {}
        return layout

    preset = deepcopy(HOME_LAYOUT_PRESETS.get(preset_key) or HOME_LAYOUT_PRESETS["standard-default"])
    if template_override:
        preset["template"] = template_override
    preset.setdefault("theme", {})
    return preset


def build_tenant_saas_admin_out(db: Session, tenant_id: int) -> dict[str, Any]:
    """管理端读取 SaaS 配置（snake_case 字段，便于后台表单）。"""
    saas = load_saas_blob(db, int(tenant_id))
    integration = get_tenant_integration_row(db, int(tenant_id))
    tenant = db.get(Tenant, int(tenant_id))
    return {
        "tenant_id": int(tenant_id),
        "tenant_code": (getattr(tenant, "code", None) or "").strip() or None,
        "app_name": _strip(saas.get("appName")) or (_strip(tenant.name) if tenant else ""),
        "default_store_id": saas.get("defaultStoreId"),
        "home_template": _strip(saas.get("homeTemplate")) or "default",
        "home_layout_preset": _strip(saas.get("homeLayoutPreset")) or "standard-default",
        "theme": saas.get("theme") if isinstance(saas.get("theme"), dict) else dict(DEFAULT_THEME),
        "features": saas.get("features") if isinstance(saas.get("features"), dict) else dict(DEFAULT_FEATURES),
        "share": saas.get("share") if isinstance(saas.get("share"), dict) else {},
        "legal": saas.get("legal") if isinstance(saas.get("legal"), dict) else {},
        "home_layout": saas.get("homeLayout") if isinstance(saas.get("homeLayout"), dict) else None,
        "subscribe_delivery_tmpl_id": _strip(integration.wx_subscribe_delivery_tmpl_id if integration else None)
        or None,
    }


def patch_tenant_saas_admin(db: Session, tenant_id: int, body) -> dict[str, Any]:
    """平台管理：更新 SaaS 展示配置（extra_json.saas + 可选 tenants.code / 订阅模板）。"""
    from fastapi import HTTPException

    from app.models.tenant import Tenant
    from app.models.tenant_integration_settings import TenantIntegrationSettings
    from app.schemas.tenant_saas import TenantSaasConfigPatchIn

    if not isinstance(body, TenantSaasConfigPatchIn):
        body = TenantSaasConfigPatchIn.model_validate(body)

    tenant = db.get(Tenant, int(tenant_id))
    if tenant is None:
        raise HTTPException(status_code=404, detail="租户不存在")

    patch = body.model_dump(exclude_unset=True)

    if "tenant_code" in patch:
        c = patch["tenant_code"]
        if c is None or str(c).strip() == "":
            tenant.code = None
        else:
            code = str(c).strip()
            dup = db.scalar(
                select(Tenant).where(Tenant.code == code, Tenant.id != int(tenant_id))
            )
            if dup is not None:
                raise HTTPException(status_code=400, detail="租户 code 已存在")
            tenant.code = code

    saas = load_saas_blob(db, int(tenant_id))
    saas_patch: dict[str, Any] = {}
    field_map = {
        "app_name": "appName",
        "default_store_id": "defaultStoreId",
        "home_template": "homeTemplate",
        "home_layout_preset": "homeLayoutPreset",
        "theme": "theme",
        "features": "features",
        "share": "share",
        "legal": "legal",
        "home_layout": "homeLayout",
    }
    for snake, camel in field_map.items():
        if snake in patch:
            val = patch[snake]
            if snake == "home_layout" and isinstance(val, dict) and not val:
                saas_patch[camel] = None
            elif val is not None:
                saas_patch[camel] = val

    if saas_patch:
        saas = merge_saas_patch(saas, saas_patch)
        save_saas_blob(db, int(tenant_id), saas)
    elif "tenant_code" in patch:
        db.commit()

    if "subscribe_delivery_tmpl_id" in patch:
        row = get_tenant_integration_row(db, int(tenant_id))
        if row is None:
            row = TenantIntegrationSettings(tenant_id=int(tenant_id))
            db.add(row)
        v = patch["subscribe_delivery_tmpl_id"]
        row.wx_subscribe_delivery_tmpl_id = (
            None if v is None or str(v).strip() == "" else str(v).strip()
        )
        db.commit()

    return build_tenant_saas_admin_out(db, int(tenant_id))
