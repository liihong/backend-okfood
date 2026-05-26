from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.deps import (
    SessionDep,
    admin_or_delivery_staff_subject,
    admin_staff_subject,
    require_admin_tenant_id,
    require_admin_tenant_store,
)
from app.core.limiter import limiter
from app.schemas.delivery_region import (
    DeliveryRegionConsultIn,
    DeliveryRegionCreateIn,
    DeliveryRegionUpdateIn,
)
from app.services.delivery_region_consult_service import consult_delivery_region
from app.services.delivery_region_map_overview_service import delivery_region_map_overview
from app.services.delivery_region_service import (
    create_delivery_region,
    delete_delivery_region,
    get_delivery_region,
    list_delivery_regions,
    update_delivery_region,
)
from app.utils.response import dump_model, success

router = APIRouter(prefix="/admin", tags=["管理端-配送区域"])


@router.get("/delivery-region-map-overview")
def delivery_region_map_overview_route(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """配送区域 + 有余额会员坐标聚合，供营业概览地图一次性加载。"""
    _, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    payload = delivery_region_map_overview(db, store_id=store_id)
    return success(data=dump_model(payload), msg="获取成功")


@router.get("/delivery-regions")
def delivery_regions_list(
    db: SessionDep,
    include_polygon: bool = False,
    admin_username: str = Depends(admin_or_delivery_staff_subject),
):
    """默认不返回 polygon_json（显著减小负载）；需要全量多边形时传 `?include_polygon=true`。"""
    tenant_id = require_admin_tenant_id(db, admin_username=admin_username)
    items = list_delivery_regions(db, include_polygon=include_polygon, tenant_id=tenant_id)
    return success(data=[dump_model(i) for i in items], msg="获取成功")


@router.get("/delivery-regions/{region_id}")
def delivery_regions_get(
    region_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_or_delivery_staff_subject),
):
    tenant_id = require_admin_tenant_id(db, admin_username=admin_username)
    item = get_delivery_region(db, region_id, tenant_id=tenant_id)
    return success(data=dump_model(item), msg="获取成功")


@router.post("/delivery-regions")
def delivery_regions_create(
    body: DeliveryRegionCreateIn,
    db: SessionDep,
    admin_username: str = Depends(admin_or_delivery_staff_subject),
):
    tenant_id = require_admin_tenant_id(db, admin_username=admin_username)
    item = create_delivery_region(db, body, tenant_id=tenant_id)
    return success(data=dump_model(item), msg="创建成功")


@router.patch("/delivery-regions/{region_id}")
def delivery_regions_patch(
    region_id: int,
    body: DeliveryRegionUpdateIn,
    db: SessionDep,
    admin_username: str = Depends(admin_or_delivery_staff_subject),
):
    tenant_id = require_admin_tenant_id(db, admin_username=admin_username)
    item = update_delivery_region(db, region_id, body, tenant_id=tenant_id)
    return success(data=dump_model(item), msg="更新成功")


@router.delete("/delivery-regions/{region_id}")
def delivery_regions_delete(
    region_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_or_delivery_staff_subject),
):
    tenant_id = require_admin_tenant_id(db, admin_username=admin_username)
    delete_delivery_region(db, region_id, tenant_id=tenant_id)
    return success(msg="已删除")


@router.post("/delivery-region/consult")
@limiter.limit("60/minute")
def delivery_region_consult(
    request: Request,
    body: DeliveryRegionConsultIn,
    db: SessionDep,
    admin_username: str = Depends(admin_or_delivery_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，用于门店锚点到咨询点的直线距离；默认 1")] = 1,
):
    """客服/后台：核验地址或坐标是否在**启用配送片区**内（与承运方无关）；关键词依赖服务端高德地理编码。"""
    _ = request
    tenant_id = require_admin_tenant_id(db, admin_username=admin_username)
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    payload = consult_delivery_region(db, tenant_id=int(tenant_id), store_id=int(sid), body=body)
    return success(data=dump_model(payload), msg="校验完成")
