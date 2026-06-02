"""抖音对接配置：租户凭证 + 门店 POI。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.douyin_life import fetch_client_token
from app.models.store import Store
from app.services.tenant_integration_service import get_tenant_integration_row


def _s(raw: str | None) -> str:
    return (raw or "").strip()


@dataclass(frozen=True)
class DouyinStoreConfig:
    """门店级抖音核销参数。"""

    poi_id: str
    account_id: str | None


@dataclass(frozen=True)
class DouyinTenantCredentials:
    client_key: str
    client_secret: str


def get_douyin_tenant_credentials(db: Session, tenant_id: int) -> DouyinTenantCredentials:
    """读取租户抖音开放平台凭证：优先 extra_json，回退环境变量。"""
    base = get_settings()
    row = get_tenant_integration_row(db, int(tenant_id))
    key = ""
    secret = ""
    if row and row.extra_json:
        try:
            obj = json.loads(row.extra_json)
            if isinstance(obj, dict):
                key = _s(obj.get("douyin_client_key"))
                secret = _s(obj.get("douyin_client_secret"))
        except json.JSONDecodeError:
            pass
    if not key:
        key = _s(getattr(base, "DOUYIN_CLIENT_KEY", None))
    if not secret:
        secret = _s(getattr(base, "DOUYIN_CLIENT_SECRET", None))
    if not key or not secret:
        raise HTTPException(status_code=503, detail="抖音开放平台凭证未配置，请联系门店管理员")
    return DouyinTenantCredentials(client_key=key, client_secret=secret)


def get_douyin_store_config(db: Session, store_id: int) -> DouyinStoreConfig:
    """读取门店 POI；未配置则不可验券。"""
    st = db.get(Store, int(store_id))
    if not st:
        raise HTTPException(status_code=404, detail="门店不存在")
    poi = _s(getattr(st, "douyin_poi_id", None))
    if not poi:
        raise HTTPException(status_code=400, detail="当前门店未配置抖音 POI，请联系管理员")
    account_id = _s(getattr(st, "douyin_account_id", None)) or None
    return DouyinStoreConfig(poi_id=poi, account_id=account_id)


def get_douyin_access_token(db: Session, tenant_id: int) -> str:
    cred = get_douyin_tenant_credentials(db, int(tenant_id))
    return fetch_client_token(client_key=cred.client_key, client_secret=cred.client_secret)
