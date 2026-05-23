"""租户对接配置：读库合并 + 平台管理读写。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.single_meal_order import SingleMealOrder
from app.models.tenant import Tenant
from app.models.tenant_integration_settings import TenantIntegrationSettings
from app.schemas.admin import TenantIntegrationSettingsOut, TenantIntegrationSettingsPatchIn
from app.services.sf_open_notify_payload import extract_shop_and_sf_order_ids


def _s(raw: str | None) -> str:
    return (raw or "").strip()


def get_tenant_integration_row(db: Session, tenant_id: int) -> TenantIntegrationSettings | None:
    return db.get(TenantIntegrationSettings, int(tenant_id))


def get_merged_wx_credentials(db: Session, tenant_id: int) -> tuple[str, str]:
    base = get_settings()
    row = get_tenant_integration_row(db, tenant_id)
    appid = _s(row.wx_mini_appid) if row else ""
    secret = _s(row.wx_mini_secret) if row else ""
    if not appid:
        appid = _s(base.WX_MINI_APPID)
    if not secret:
        secret = _s(base.WX_MINI_SECRET)
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
    base = get_settings()
    row = get_tenant_integration_row(db, tenant_id)
    appid = _s(row.wx_mini_appid) if row else ""
    mch = _s(row.wechat_pay_mch_id) if row else ""
    key = _s(row.wechat_pay_api_key) if row else ""
    notify = _s(row.wechat_pay_notify_url) if row else ""
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
    if not appid:
        appid = _s(base.WX_MINI_APPID)
    if not mch:
        mch = _s(base.WECHAT_PAY_MCH_ID)
    if not key:
        key = _s(base.WECHAT_PAY_API_KEY)
    if not notify:
        notify = _s(base.WECHAT_PAY_NOTIFY_URL)
    return MergedPayConfig(
        wx_mini_appid=appid,
        wechat_pay_mch_id=mch,
        wechat_pay_api_key=key,
        wechat_pay_notify_url=notify,
        wechat_pay_ssl_cert_path=cert_merged,
        wechat_pay_ssl_key_path=keyp_merged,
    )


def wechat_pay_misconfiguration_detail_merged(cfg: MergedPayConfig) -> str | None:
    if not cfg.wechat_pay_mch_id:
        return "未配置微信支付商户号（租户或全局 WECHAT_PAY_MCH_ID）"
    if not cfg.wechat_pay_api_key:
        return "未配置微信 APIv2 密钥（租户或全局 WECHAT_PAY_API_KEY）"
    if len(cfg.wechat_pay_api_key) != 32:
        return (
            f"WECHAT_PAY_API_KEY 必须为 32 位，当前 {len(cfg.wechat_pay_api_key)} 位。"
            "请到 pay.weixin.qq.com 核对后填入租户对接配置或全局 .env"
        )
    if not cfg.wechat_pay_notify_url:
        return "未配置支付回调 notify_url（租户或全局 WECHAT_PAY_NOTIFY_URL）"
    if not cfg.wx_mini_appid:
        return "未配置小程序 AppId（租户或全局 WX_MINI_APPID）"
    return None


def resolve_tenant_id_for_wechat_out_trade_no(db: Session, out_trade_no: str) -> int:
    otn = _s(out_trade_no)
    if not otn:
        return int(get_settings().DEFAULT_TENANT_ID)
    for model in (SingleMealOrder, MemberCardOrder):
        tid = db.scalar(select(model.tenant_id).where(model.out_trade_no == otn).limit(1))
        if tid is not None:
            return int(tid)
    return int(get_settings().DEFAULT_TENANT_ID)


def merged_sf_integration_namespace(db: Session, tenant_id: int) -> SimpleNamespace:
    """供顺丰预览/推单/取消使用：与现有代码中 gset 属性名一致。"""
    base = get_settings()
    row = get_tenant_integration_row(db, tenant_id)
    ns = SimpleNamespace()

    ns.SF_OPEN_DEV_ID = (
        int(row.sf_open_dev_id)
        if row and row.sf_open_dev_id is not None
        else int(base.SF_OPEN_DEV_ID or 0)
    )
    sec = _s(row.sf_open_secret) if row else ""
    ns.SF_OPEN_SECRET = sec if sec else _s(base.SF_OPEN_SECRET)
    shop = _s(row.sf_open_shop_id) if row else ""
    ns.SF_OPEN_SHOP_ID = shop if shop else _s(base.SF_OPEN_SHOP_ID)
    ns.SF_OPEN_SHOP_TYPE = (
        int(row.sf_open_shop_type)
        if row and row.sf_open_shop_type is not None
        else int(base.SF_OPEN_SHOP_TYPE or 1)
    )
    pp = _s(row.sf_pickup_phone) if row else ""
    ns.SF_PICKUP_PHONE = pp if pp else _s(base.SF_PICKUP_PHONE)
    pa = _s(row.sf_pickup_address) if row else ""
    ns.SF_PICKUP_ADDRESS = pa if pa else _s(base.SF_PICKUP_ADDRESS)
    cn = _s(row.sf_city_name) if row else ""
    ns.SF_CITY_NAME = cn if cn else _s(base.SF_CITY_NAME)

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
    """顺丰回调验签密钥：须与 ``sf_same_city_push`` 门店所属租户配置一致。

    开放平台报文常为嵌套 JSON（字段在 ``data``/``result``/``post_data`` 内）；仅用顶层取值会走错密钥并验签失败。
    """
    keys = resolve_sf_notify_app_key_candidates(db, payload)
    return keys[0] if keys else _s(get_settings().SF_OPEN_SECRET)


def resolve_sf_notify_app_key_candidates(db: Session, payload: dict[str, Any] | None) -> list[str]:
    """按推单租户密钥优先、全局 .env 密钥兜底的验签密钥候选（去重保序）。"""
    from app.services.sf_open_notify_payload import normalize_sf_callback_payload

    base = get_settings()
    global_key = _s(base.SF_OPEN_SECRET)
    out: list[str] = []

    def add(k: str) -> None:
        kk = _s(k)
        if kk and kk not in out:
            out.append(kk)

    if not payload or not isinstance(payload, dict):
        add(global_key)
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

    if push_id is None:
        add(global_key)
        return out
    prow = db.get(SfSameCityPush, int(push_id))
    if prow and prow.store_id:
        from app.models.store import Store

        st = db.get(Store, int(prow.store_id))
        if st:
            row = get_tenant_integration_row(db, int(st.tenant_id))
            if row and _s(row.sf_open_secret):
                add(_s(row.sf_open_secret))
    add(global_key)
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
