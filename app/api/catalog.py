from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import SessionDep, public_store_dep, PublicStoreContext
from app.services.client.retail_share_poster_service import build_retail_share_poster
from app.services.retail.retail_catalog_public import (
    build_sku_lookup_from_menu,
    get_retail_sku_public,
    get_retail_spu_detail_public,
    list_retail_menu_public,
)
from app.utils.response import success

router = APIRouter(prefix="/catalog", tags=["商品目录"])


@router.get("/retail-menu")
def catalog_retail_menu(db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)):
    """小程序菜单页：门店零售分类及上架商品 SPU（无需登录）。"""
    items = list_retail_menu_public(db, store_id=int(store_ctx.store_id))
    return success(data=items, msg="获取成功")


@router.get("/retail-spu/{spu_id}")
def catalog_retail_spu_detail(
    spu_id: int,
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
):
    """小程序商品详情：SPU + 可售 SKU 列表。"""
    detail = get_retail_spu_detail_public(db, store_id=int(store_ctx.store_id), spu_id=int(spu_id))
    if not detail:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    return success(data=detail, msg="获取成功")


@router.get("/retail-spu/{spu_id}/share-poster")
def catalog_retail_spu_share_poster(
    spu_id: int,
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
    env_version: Literal["release", "trial", "develop"] = Query(
        "release",
        description="太阳码打开的小程序版本：release / trial / develop",
    ),
):
    """商品分享海报素材（太阳码 + 门店/商品字段）。无需登录。"""
    data = build_retail_share_poster(
        db,
        store_id=int(store_ctx.store_id),
        tenant_id=int(store_ctx.tenant_id),
        spu_id=int(spu_id),
        env_version=env_version,
    )
    return success(data=data, msg="获取成功")


@router.get("/retail-sku-lookup")
def catalog_retail_sku_lookup(db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)):
    """购物车同步：SKU id → 最新价格/库存/展示名。"""
    lookup = build_sku_lookup_from_menu(db, store_id=int(store_ctx.store_id))
    return success(data=lookup, msg="获取成功")


@router.get("/retail-sku/{sku_id}")
def catalog_retail_sku_detail(
    sku_id: int,
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
):
    """单 SKU 公开信息（立即购买结算页等）。"""
    detail = get_retail_sku_public(db, store_id=int(store_ctx.store_id), sku_id=int(sku_id))
    if not detail:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    return success(data=detail, msg="获取成功")
