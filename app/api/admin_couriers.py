from fastapi import APIRouter, Depends

from app.core.deps import SessionDep, admin_or_delivery_staff_subject, require_admin_tenant_id
from app.schemas.admin_courier import CourierCreateIn, CourierPinResetIn, CourierUpdateIn
from app.services.admin.courier_admin_service import (
    create_courier_admin,
    list_couriers_admin,
    reset_courier_pin,
    update_courier_admin,
)
from app.utils.response import dump_model, success

router = APIRouter(prefix="/admin", tags=["管理端-配送员"])


@router.get("/couriers")
def couriers_list(db: SessionDep, admin_username: str = Depends(admin_or_delivery_staff_subject)):
    tid = require_admin_tenant_id(db, admin_username=admin_username)
    items = list_couriers_admin(db, tenant_id=tid)
    return success(data=[dump_model(i) for i in items], msg="获取成功")


@router.post("/couriers")
def couriers_create(
    body: CourierCreateIn, db: SessionDep, admin_username: str = Depends(admin_or_delivery_staff_subject)
):
    tid = require_admin_tenant_id(db, admin_username=admin_username)
    item = create_courier_admin(db, body, tenant_id=tid)
    return success(data=dump_model(item), msg="创建成功")


@router.patch("/couriers/{courier_id}")
def couriers_patch(
    courier_id: str,
    body: CourierUpdateIn,
    db: SessionDep,
    admin_username: str = Depends(admin_or_delivery_staff_subject),
):
    tid = require_admin_tenant_id(db, admin_username=admin_username)
    item = update_courier_admin(db, courier_id, body, tenant_id=tid)
    return success(data=dump_model(item), msg="更新成功")


@router.post("/couriers/{courier_id}/pin")
def couriers_reset_pin(
    courier_id: str,
    body: CourierPinResetIn,
    db: SessionDep,
    admin_username: str = Depends(admin_or_delivery_staff_subject),
):
    tid = require_admin_tenant_id(db, admin_username=admin_username)
    reset_courier_pin(db, courier_id, body.pin, tenant_id=tid)
    return success(msg="PIN 已更新")
