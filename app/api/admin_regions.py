from fastapi import APIRouter, Depends

from app.core.deps import SessionDep, admin_subject
from app.schemas.delivery_region import DeliveryRegionCreateIn, DeliveryRegionUpdateIn
from app.services.delivery_region_service import (
    create_delivery_region,
    delete_delivery_region,
    get_delivery_region,
    list_delivery_regions,
    update_delivery_region,
)
from app.utils.response import dump_model, success

router = APIRouter(prefix="/admin", tags=["管理端-配送区域"])


@router.get("/delivery-regions")
def delivery_regions_list(db: SessionDep, _admin: str = Depends(admin_subject)):
    items = list_delivery_regions(db)
    return success(data=[dump_model(i) for i in items], msg="获取成功")


@router.get("/delivery-regions/{region_id}")
def delivery_regions_get(region_id: int, db: SessionDep, _admin: str = Depends(admin_subject)):
    item = get_delivery_region(db, region_id)
    return success(data=dump_model(item), msg="获取成功")


@router.post("/delivery-regions")
def delivery_regions_create(body: DeliveryRegionCreateIn, db: SessionDep, _admin: str = Depends(admin_subject)):
    item = create_delivery_region(db, body)
    return success(data=dump_model(item), msg="创建成功")


@router.patch("/delivery-regions/{region_id}")
def delivery_regions_patch(region_id: int, body: DeliveryRegionUpdateIn, db: SessionDep, _admin: str = Depends(admin_subject)):
    item = update_delivery_region(db, region_id, body)
    return success(data=dump_model(item), msg="更新成功")


@router.delete("/delivery-regions/{region_id}")
def delivery_regions_delete(region_id: int, db: SessionDep, _admin: str = Depends(admin_subject)):
    delete_delivery_region(db, region_id)
    return success(msg="已删除")
