from fastapi import APIRouter, Depends

from app.core.deps import SessionDep, admin_or_delivery_staff_subject, admin_subject
from app.schemas.delivery_region import DeliveryRegionCreateIn, DeliveryRegionUpdateIn
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
def delivery_region_map_overview_route(db: SessionDep, _admin: str = Depends(admin_subject)):
    """配送区域 + 有余额会员坐标聚合，供营业概览地图一次性加载。"""
    payload = delivery_region_map_overview(db)
    return success(data=dump_model(payload), msg="获取成功")


@router.get("/delivery-regions")
def delivery_regions_list(
    db: SessionDep,
    include_polygon: bool = False,
    _admin: str = Depends(admin_or_delivery_staff_subject),
):
    """默认不返回 polygon_json（显著减小负载）；需要全量多边形时传 `?include_polygon=true`。"""
    items = list_delivery_regions(db, include_polygon=include_polygon)
    return success(data=[dump_model(i) for i in items], msg="获取成功")


@router.get("/delivery-regions/{region_id}")
def delivery_regions_get(region_id: int, db: SessionDep, _admin: str = Depends(admin_or_delivery_staff_subject)):
    item = get_delivery_region(db, region_id)
    return success(data=dump_model(item), msg="获取成功")


@router.post("/delivery-regions")
def delivery_regions_create(body: DeliveryRegionCreateIn, db: SessionDep, _admin: str = Depends(admin_or_delivery_staff_subject)):
    item = create_delivery_region(db, body)
    return success(data=dump_model(item), msg="创建成功")


@router.patch("/delivery-regions/{region_id}")
def delivery_regions_patch(region_id: int, body: DeliveryRegionUpdateIn, db: SessionDep, _admin: str = Depends(admin_or_delivery_staff_subject)):
    item = update_delivery_region(db, region_id, body)
    return success(data=dump_model(item), msg="更新成功")


@router.delete("/delivery-regions/{region_id}")
def delivery_regions_delete(region_id: int, db: SessionDep, _admin: str = Depends(admin_or_delivery_staff_subject)):
    delete_delivery_region(db, region_id)
    return success(msg="已删除")
