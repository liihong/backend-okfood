"""租户对接配置：读库合并 + 平台管理读写。

多租户合并规则（见 ``app.core.tenant_scope``）：
- **主租户**（``DEFAULT_TENANT_ID``）：未填字段可回退全局 ``.env``，兼容历史单店。
- **其它租户**：禁止回退全局配置，避免主租户密钥/商户号暴露或支付串账。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tenant_scope import (
    TENANT_INTEGRATION_INCOMPLETE_HINT,
    allows_global_env_fallback,
    legacy_default_tenant_id,
    merge_tenant_field_or_global,
    merge_tenant_int_or_global,
)
from app.models.member_card_order import MemberCardOrder
from app.models.single_meal_order import SingleMealOrder
from app.models.tenant import Tenant
from app.models.tenant_integration_settings import TenantIntegrationSettings
from app.schemas.admin import TenantIntegrationSettingsOut, TenantIntegrationSettingsPatchIn
from app.services.delivery.sf_open_notify_payload import extract_shop_and_sf_order_ids


def _s(raw: str | None) -> str:
    return (raw or "").strip()


def get_tenant_integration_row(db: Session, tenant_id: int) -> TenantIntegrationSettings | None:
    return db.get(TenantIntegrationSettings, int(tenant_id))


def get_merged_wx_credentials(db: Session, tenant_id: int) -> tuple[str, str]:
    """小程序 AppId/Secret：非主租户缺省不回退全局，由 ``wx_mini_configured_for_tenant`` 拦截登录。"""
    base = get_settings()
    row = get_tenant_integration_row(db, tenant_id)
    tid = int(tenant_id)
    appid = merge_tenant_field_or_global(
        row.wx_mini_appid if row else None, base.WX_MINI_APPID, tenant_id=tid
    )
    secret = merge_tenant_field_or_global(
        row.wx_mini_secret if row else None, base.WX_MINI_SECRET, tenant_id=tid
    )
    return appid, secret


@dataclass(frozen=True)
class MergedPayConfig:
    wx_mini_appid: str
    wechat_pay_mch_id: str
    wechat_pay_api_key: str
    wechat_pay_notify_url: str
    wechat_pay_ssl_cert_path: str = ""
    wechat_pay_ssl_key_path: str = ""


def get_merged_pay_config(db: Session, tenant_id: int, store_id: int | None = None) -> MergedPayConfig:
    """支付配置合并：非主租户须独立配置商户号与 API 密钥，禁止串用主租户 .env。"""
    base = get_settings()
    row = get_tenant_integration_row(db, tenant_id)
    tid = int(tenant_id)
    appid = merge_tenant_field_or_global(
        row.wx_mini_appid if row else None, base.WX_MINI_APPID, tenant_id=tid
    )
    mch = merge_tenant_field_or_global(
        row.wechat_pay_mch_id if row else None, base.WECHAT_PAY_MCH_ID, tenant_id=tid
    )
    key = merge_tenant_field_or_global(
        row.wechat_pay_api_key if row else None, base.WECHAT_PAY_API_KEY, tenant_id=tid
    )
    notify = merge_tenant_field_or_global(
        row.wechat_pay_notify_url if row else None, base.WECHAT_PAY_NOTIFY_URL, tenant_id=tid
    )
    cert_t = _s(row.wechat_pay_ssl_cert_path) if row else ""
    keyp_t = _s(row.wechat_pay_ssl_key_path) if row else ""
    cert_s, keyp_s = "", ""
    if store_id is not None:
        from app.models.store import Store as StoreModel

        st_row = db.get(StoreModel, int(store_id))
        if st_row is not None:
            cert_s = _s(getattr(st_row, "wechat_pay_ssl_cert_path", None))
            keyp_s = _s(getattr(st_row, "wechat_pay_ssl_key_path", None))
    cert_merged = cert_s or cert_t
    keyp_merged = keyp_s or keyp_t
    return MergedPayConfig(
        wx_mini_appid=appid,
        wechat_pay_mch_id=mch,
        wechat_pay_api_key=key,
        wechat_pay_notify_url=notify,
        wechat_pay_ssl_cert_path=cert_merged,
        wechat_pay_ssl_key_path=keyp_merged,
    )


def wechat_pay_misconfiguration_detail_merged(
    cfg: MergedPayConfig, *, tenant_id: int | None = None
) -> str | None:
    """支付配置完整性检查；非主租户缺项时附带对接设置引导文案。"""
    hint_suffix = ""
    if tenant_id is not None and not allows_global_env_fallback(int(tenant_id)):
        hint_suffix = f"；{TENANT_INTEGRATION_INCOMPLETE_HINT}"

    if not cfg.wechat_pay_mch_id:
        return f"未配置微信支付商户号{hint_suffix}"
    if not cfg.wechat_pay_api_key:
        return f"未配置微信 APIv2 密钥{hint_suffix}"
    if len(cfg.wechat_pay_api_key) != 32:
        return (
            f"WECHAT_PAY_API_KEY 必须为 32 位，当前 {len(cfg.wechat_pay_api_key)} 位。"
            f"请到 pay.weixin.qq.com 核对后填入租户对接配置{hint_suffix}"
        )
    if not cfg.wechat_pay_notify_url:
        return f"未配置支付回调 notify_url{hint_suffix}"
    if not cfg.wx_mini_appid:
        return f"未配置小程序 AppId{hint_suffix}"
    return None


def assert_tenant_pay_config_ready(
    db: Session, tenant_id: int, store_id: int | None = None
) -> MergedPayConfig:
    """下单/退款前校验：配置不全时 503，非主租户不会落到主租户支付密钥。"""
    cfg = get_merged_pay_config(db, int(tenant_id), store_id=store_id)
    detail = wechat_pay_misconfiguration_detail_merged(cfg, tenant_id=int(tenant_id))
    if detail:
        raise HTTPException(status_code=503, detail=detail)
    return cfg


def resolve_tenant_id_for_wechat_out_trade_no(
    db: Session, out_trade_no: str, *, allow_legacy_default_fallback: bool = False
) -> int | None:
    """
    按商户单号反查订单所属租户。

    - 找到订单：返回其 ``tenant_id``（支付验签/入账须用该租户密钥）。
    - 未找到：**禁止**默认回落主租户（避免租户 2 回调误用租户 1 密钥）；仅当
      ``allow_legacy_default_fallback=True`` 且调用方明确兼容单店历史行为时才回落。
    """
    otn = _s(out_trade_no)
    if not otn:
        if allow_legacy_default_fallback:
            return legacy_default_tenant_id()
        return None
    for model in (SingleMealOrder, MemberCardOrder):
        tid = db.scalar(select(model.tenant_id).where(model.out_trade_no == otn).limit(1))
        if tid is not None:
            return int(tid)
    if allow_legacy_default_fallback:
        return legacy_default_tenant_id()
    return None


def list_tenant_ids_by_wechat_mch_id(db: Session, mch_id: str) -> list[int]:
    """回调报文中的 ``mch_id`` → 配置了该商户号的租户 id 列表（去重保序）。"""
    mid = _s(mch_id)
    if not mid:
        return []
    out: list[int] = []
    base = get_settings()
    global_mch = _s(base.WECHAT_PAY_MCH_ID)

    def add(tid: int) -> None:
        t = int(tid)
        if t not in out:
            out.append(t)

    rows = db.scalars(select(TenantIntegrationSettings)).all()
    for row in rows:
        m = _s(row.wechat_pay_mch_id)
        if m and m == mid:
            add(int(row.tenant_id))
    if global_mch and global_mch == mid:
        add(legacy_default_tenant_id())
    return out


def resolve_wechat_pay_notify_api_key_candidates(
    db: Session, data: dict[str, str]
) -> list[str]:
    """
    微信异步通知验签密钥候选（去重保序）。

    优先级：
    1. 商户单号命中订单 → 该租户密钥；
    2. 报文 ``mch_id`` 命中租户对接配置；
    3. 各租户已配置的 API 密钥（覆盖「订单尚未入库」的竞态回调）；
    4. 主租户全局 .env 密钥（仅主租户兼容）。
    """
    out: list[str] = []

    def add(key: str | None) -> None:
        kk = _s(key)
        if kk and kk not in out:
            out.append(kk)

    otn = _s(data.get("out_trade_no"))
    mch_id = _s(data.get("mch_id"))

    tid = resolve_tenant_id_for_wechat_out_trade_no(db, otn, allow_legacy_default_fallback=False)
    if tid is not None:
        add(get_merged_pay_config(db, tid).wechat_pay_api_key)

    for t in list_tenant_ids_by_wechat_mch_id(db, mch_id):
        add(get_merged_pay_config(db, t).wechat_pay_api_key)

    for row in db.scalars(select(TenantIntegrationSettings)).all():
        add(row.wechat_pay_api_key)

    base = get_settings()
    if allows_global_env_fallback(legacy_default_tenant_id()):
        add(base.WECHAT_PAY_API_KEY)

    return out


def merged_sf_integration_namespace(db: Session, tenant_id: int) -> SimpleNamespace:
    """顺丰预览/推单参数：非主租户缺省不回退全局，避免串用主租户顺丰账号。"""
    base = get_settings()
    row = get_tenant_integration_row(db, tenant_id)
    tid = int(tenant_id)
    ns = SimpleNamespace()

    ns.SF_OPEN_DEV_ID = merge_tenant_int_or_global(
        row.sf_open_dev_id if row else None,
        int(base.SF_OPEN_DEV_ID or 0),
        tenant_id=tid,
    )
    ns.SF_OPEN_SECRET = merge_tenant_field_or_global(
        row.sf_open_secret if row else None, base.SF_OPEN_SECRET, tenant_id=tid
    )
    ns.SF_OPEN_SHOP_ID = merge_tenant_field_or_global(
        row.sf_open_shop_id if row else None, base.SF_OPEN_SHOP_ID, tenant_id=tid
    )
    ns.SF_OPEN_SHOP_TYPE = merge_tenant_int_or_global(
        row.sf_open_shop_type if row else None,
        int(base.SF_OPEN_SHOP_TYPE or 1),
        tenant_id=tid,
    )
    ns.SF_PICKUP_PHONE = merge_tenant_field_or_global(
        row.sf_pickup_phone if row else None, base.SF_PICKUP_PHONE, tenant_id=tid
    )
    ns.SF_PICKUP_ADDRESS = merge_tenant_field_or_global(
        row.sf_pickup_address if row else None, base.SF_PICKUP_ADDRESS, tenant_id=tid
    )
    ns.SF_CITY_NAME = merge_tenant_field_or_global(
        row.sf_city_name if row else None, base.SF_CITY_NAME, tenant_id=tid
    )

    ns.SF_ORDER_SOURCE = base.SF_ORDER_SOURCE
    ns.SF_API_VERSION = base.SF_API_VERSION
    ns.SF_VEHICLE_TYPE_CODE = base.SF_VEHICLE_TYPE_CODE
    ns.SF_DEFAULT_PRODUCT_TYPE = base.SF_DEFAULT_PRODUCT_TYPE
    ns.SF_KG_PER_MEAL_UNIT = base.SF_KG_PER_MEAL_UNIT
    ns.SF_PRODUCT_CATEGORY_LABEL = base.SF_PRODUCT_CATEGORY_LABEL
    ns.SF_DEFAULT_VEHICLE_TYPE = base.SF_DEFAULT_VEHICLE_TYPE
    ns.DEFAULT_STORE_ID = base.DEFAULT_STORE_ID
    return ns


def resolve_sf_notify_app_key(db: Session, payload: dict[str, Any] | None) -> str:
    """顺丰回调验签密钥：取候选列表首项。"""
    keys = resolve_sf_notify_app_key_candidates(db, payload)
    if keys:
        return keys[0]
    base = get_settings()
    if allows_global_env_fallback(legacy_default_tenant_id()):
        return _s(base.SF_OPEN_SECRET)
    return ""


def resolve_sf_notify_app_key_candidates(db: Session, payload: dict[str, Any] | None) -> list[str]:
    """
    顺丰回调验签密钥候选。

    - 能定位推单/门店：仅用该租户密钥；主租户可追加全局兜底。
    - 无法定位：遍历各租户已配置密钥 + 主租户全局（不用主租户密钥替非主租户验签）。
    """
    from app.services.delivery.sf_open_notify_payload import normalize_sf_callback_payload

    base = get_settings()
    out: list[str] = []

    def add(k: str) -> None:
        kk = _s(k)
        if kk and kk not in out:
            out.append(kk)

    if not payload or not isinstance(payload, dict):
        for row in db.scalars(select(TenantIntegrationSettings)).all():
            add(row.sf_open_secret)
        if allows_global_env_fallback(legacy_default_tenant_id()):
            add(base.SF_OPEN_SECRET)
        return out

    norm = normalize_sf_callback_payload(payload)
    shop_s, sf_s = extract_shop_and_sf_order_ids(norm)
    shop_oid = _s(str(shop_s or "").strip())
    sf_id = _s(str(sf_s or "").strip())

    from app.models.sf_same_city_push import SfSameCityPush

    push_id = None
    if shop_oid:
        push_id = db.scalar(
            select(SfSameCityPush.id)
            .where(SfSameCityPush.shop_order_id == shop_oid)
            .order_by(SfSameCityPush.id.desc())
            .limit(1)
        )
    if push_id is None and sf_id:
        push_id = db.scalar(
            select(SfSameCityPush.id)
            .where(or_(SfSameCityPush.sf_order_id == sf_id, SfSameCityPush.sf_bill_id == sf_id))
            .order_by(SfSameCityPush.id.desc())
            .limit(1)
        )

    if push_id is not None:
        prow = db.get(SfSameCityPush, int(push_id))
        if prow and prow.store_id:
            from app.models.store import Store

            st = db.get(Store, int(prow.store_id))
            if st:
                row = get_tenant_integration_row(db, int(st.tenant_id))
                if row and _s(row.sf_open_secret):
                    add(_s(row.sf_open_secret))
                if allows_global_env_fallback(int(st.tenant_id)):
                    add(base.SF_OPEN_SECRET)
        return out

    for row in db.scalars(select(TenantIntegrationSettings)).all():
        add(row.sf_open_secret)
    if allows_global_env_fallback(legacy_default_tenant_id()):
        add(base.SF_OPEN_SECRET)
    return out


def get_tenant_integration_admin_out(db: Session, tenant_id: int) -> TenantIntegrationSettingsOut:
    if not db.get(Tenant, int(tenant_id)):
        raise HTTPException(status_code=404, detail="租户不存在")
    row = get_tenant_integration_row(db, tenant_id)
    if not row:
        return TenantIntegrationSettingsOut(tenant_id=int(tenant_id))
    return TenantIntegrationSettingsOut(
        tenant_id=int(tenant_id),
        wx_mini_appid=_s(row.wx_mini_appid) or None,
        wx_mini_secret_set=bool(_s(row.wx_mini_secret)),
        wechat_pay_mch_id=_s(row.wechat_pay_mch_id) or None,
        wechat_pay_api_key_set=bool(_s(row.wechat_pay_api_key)),
        wechat_pay_notify_url=_s(row.wechat_pay_notify_url) or None,
        wechat_pay_ssl_cert_path=_s(row.wechat_pay_ssl_cert_path) or None,
        wechat_pay_ssl_key_path=_s(row.wechat_pay_ssl_key_path) or None,
        wx_subscribe_delivery_tmpl_id=_s(row.wx_subscribe_delivery_tmpl_id) or None,
        wx_subscribe_renew_tmpl_id=_s(row.wx_subscribe_renew_tmpl_id) or None,
        sf_open_dev_id=row.sf_open_dev_id,
        sf_open_secret_set=bool(_s(row.sf_open_secret)),
        sf_open_shop_id=_s(row.sf_open_shop_id) or None,
        sf_open_shop_type=row.sf_open_shop_type,
        sf_pickup_phone=_s(row.sf_pickup_phone) or None,
        sf_pickup_address=_s(row.sf_pickup_address) or None,
        sf_city_name=_s(row.sf_city_name) or None,
        extra_json=_s(row.extra_json) or None,
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def patch_tenant_integration_admin(
    db: Session, tenant_id: int, body: TenantIntegrationSettingsPatchIn
) -> TenantIntegrationSettingsOut:
    if not db.get(Tenant, int(tenant_id)):
        raise HTTPException(status_code=404, detail="租户不存在")
    row = get_tenant_integration_row(db, tenant_id)
    if not row:
        row = TenantIntegrationSettings(tenant_id=int(tenant_id))
        db.add(row)

    patch = body.model_dump(exclude_unset=True)

    def set_opt_str(col: str, key: str) -> None:
        if key not in patch:
            return
        v = patch[key]
        if v is None:
            setattr(row, col, None)
        else:
            s = str(v).strip()
            setattr(row, col, s if s else None)

    set_opt_str("wx_mini_appid", "wx_mini_appid")
    if "wx_mini_secret" in patch:
        v = patch["wx_mini_secret"]
        if v is None or str(v).strip() == "":
            row.wx_mini_secret = None
        else:
            row.wx_mini_secret = str(v).strip()

    set_opt_str("wechat_pay_mch_id", "wechat_pay_mch_id")
    if "wechat_pay_api_key" in patch:
        v = patch["wechat_pay_api_key"]
        if v is None or str(v).strip() == "":
            row.wechat_pay_api_key = None
        else:
            row.wechat_pay_api_key = str(v).strip()

    set_opt_str("wechat_pay_notify_url", "wechat_pay_notify_url")
    set_opt_str("wechat_pay_ssl_cert_path", "wechat_pay_ssl_cert_path")
    set_opt_str("wechat_pay_ssl_key_path", "wechat_pay_ssl_key_path")
    set_opt_str("wx_subscribe_delivery_tmpl_id", "wx_subscribe_delivery_tmpl_id")
    set_opt_str("wx_subscribe_renew_tmpl_id", "wx_subscribe_renew_tmpl_id")

    if "sf_open_dev_id" in patch:
        v = patch["sf_open_dev_id"]
        row.sf_open_dev_id = None if v is None else int(v)

    if "sf_open_secret" in patch:
        v = patch["sf_open_secret"]
        if v is None or str(v).strip() == "":
            row.sf_open_secret = None
        else:
            row.sf_open_secret = str(v).strip()

    set_opt_str("sf_open_shop_id", "sf_open_shop_id")
    if "sf_open_shop_type" in patch:
        v = patch["sf_open_shop_type"]
        row.sf_open_shop_type = None if v is None else int(v)

    set_opt_str("sf_pickup_phone", "sf_pickup_phone")
    set_opt_str("sf_pickup_address", "sf_pickup_address")
    set_opt_str("sf_city_name", "sf_city_name")

    if "extra_json" in patch:
        v = patch["extra_json"]
        if v is None:
            row.extra_json = None
        else:
            s = str(v).strip()
            if not s:
                row.extra_json = None
            else:
                try:
                    json.loads(s)
                except json.JSONDecodeError:
                    raise HTTPException(status_code=400, detail="extra_json 须为合法 JSON") from None
                row.extra_json = s

    db.commit()
    db.refresh(row)
    return get_tenant_integration_admin_out(db, tenant_id)
