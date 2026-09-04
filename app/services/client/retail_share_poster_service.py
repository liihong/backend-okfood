"""零售商品分享海报：门店信息 + 商品字段 + 太阳码。"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.integrations.wechat_mini import WeChatMiniError, get_unlimited_wxacode
from app.services.retail.retail_catalog_public import get_retail_spu_detail_public
from app.services.shared.store_config_service import get_store_config

logger = logging.getLogger(__name__)

# 扫码落地页（无前导 /）；scene 最长 32 字符
RETAIL_SHARE_WXACODE_PAGE = "packageOrder/pages/retailProductDetail/retailProductDetail"
RETAIL_SHARE_RECOMMEND_TEXT = "给你推荐了一个好东西"

# (tenant_id, scene, env_version) -> (png_bytes, expires_at)
_wxacode_cache: dict[tuple[int, str, str], tuple[bytes, float]] = {}
_WXACODE_TTL_SEC = 7 * 24 * 3600


def encode_retail_share_scene(spu_id: int) -> str:
    """编码太阳码 scene，扫码后详情页用 ``parse_retail_share_scene`` 还原。"""
    sid = int(spu_id)
    if sid < 1:
        raise ValueError("spu_id 无效")
    scene = f"r{sid}"
    if len(scene) > 32:
        raise ValueError("spu_id 过长，无法写入小程序码")
    return scene


def parse_retail_share_scene(scene: str | None) -> int | None:
    """解析太阳码 scene，成功返回 SPU id。"""
    raw = (scene or "").strip()
    if not raw:
        return None
    try:
        from urllib.parse import unquote

        raw = unquote(raw)
    except Exception:
        pass
    if raw[:1] in ("r", "R") and raw[1:].isdigit():
        n = int(raw[1:])
        return n if n >= 1 else None
    if raw.isdigit():
        n = int(raw)
        return n if n >= 1 else None
    return None


def _cache_get(tenant_id: int, scene: str, env: str) -> bytes | None:
    key = (int(tenant_id), scene, env)
    ent = _wxacode_cache.get(key)
    if not ent:
        return None
    blob, exp = ent
    if exp <= time.time():
        _wxacode_cache.pop(key, None)
        return None
    return blob


def _cache_put(tenant_id: int, scene: str, env: str, blob: bytes) -> None:
    _wxacode_cache[(int(tenant_id), scene, env)] = (blob, time.time() + _WXACODE_TTL_SEC)


def _fetch_wxacode_png(
    db: Session, *, tenant_id: int, scene: str, env_version: str
) -> bytes:
    cached = _cache_get(tenant_id, scene, env_version)
    if cached:
        return cached
    png = get_unlimited_wxacode(
        scene=scene,
        page=RETAIL_SHARE_WXACODE_PAGE,
        env_version=env_version,
        width=430,
        is_hyaline=True,
        db=db,
        tenant_id=int(tenant_id),
    )
    _cache_put(tenant_id, scene, env_version, png)
    return png


def build_retail_share_poster(
    db: Session,
    *,
    store_id: int,
    tenant_id: int,
    spu_id: int,
    env_version: str = "release",
) -> dict[str, Any]:
    """组装海报素材：商品/门店字段 + 太阳码 Base64。"""
    env = (env_version or "release").strip() or "release"
    if env not in ("release", "trial", "develop"):
        raise HTTPException(status_code=400, detail="env_version 无效")

    detail = get_retail_spu_detail_public(db, store_id=int(store_id), spu_id=int(spu_id))
    if not detail:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")

    cfg = get_store_config(db, store_id=int(store_id))
    store_name = (cfg.store_name or "").strip() or "OK饭"
    logo = (cfg.store_logo_url or "").strip() or None
    scene = encode_retail_share_scene(int(detail["id"]))

    try:
        png = _fetch_wxacode_png(db, tenant_id=int(tenant_id), scene=scene, env_version=env)
    except WeChatMiniError as e:
        logger.warning(
            "零售分享海报小程序码失败 tenant_id=%s spu_id=%s env=%s err=%s",
            tenant_id,
            spu_id,
            env,
            e,
        )
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    return {
        "spu_id": int(detail["id"]),
        "store_name": store_name,
        "store_logo_url": logo,
        "recommend_text": RETAIL_SHARE_RECOMMEND_TEXT,
        "title": detail.get("title") or "",
        "subtitle": detail.get("subtitle"),
        "price_yuan": detail.get("price_min_yuan"),
        "cover_image_url": detail.get("cover_image_url"),
        "wxacode_base64": base64.b64encode(png).decode("ascii"),
        "scene": scene,
    }
