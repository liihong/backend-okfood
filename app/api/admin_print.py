"""管理端：门店打印机与打印任务 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store
from app.schemas.store_print import (
    StorePrintJobCreateIn,
    StorePrintProfileCreateIn,
    StorePrintProfilePatchIn,
    StorePrintSceneSettingsPutIn,
    TenantPrintCloudCredentialsPatchIn,
)
from app.services.admin import store_print_service as svc
from app.utils.response import dump_model, success

router = APIRouter(prefix="/admin", tags=["管理端-打印机"])


@router.get("/store-print/cloud-credentials")
def get_print_cloud_credentials(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    tid, _ = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.get_tenant_print_cloud_credentials_out(db, tid)
    return success(data=dump_model(data), msg="获取成功")


@router.put("/store-print/cloud-credentials")
def put_print_cloud_credentials(
    db: SessionDep,
    body: TenantPrintCloudCredentialsPatchIn,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    tid, _ = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.patch_tenant_print_cloud_credentials(db, tid, body)
    return success(data=dump_model(data), msg="保存成功")


@router.get("/store-print/profiles")
def list_print_profiles(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    items = svc.list_store_print_profiles(db, store_id=sid)
    return success(data=[dump_model(i) for i in items], msg="获取成功")


@router.post("/store-print/profiles")
def create_print_profile(
    db: SessionDep,
    body: StorePrintProfileCreateIn,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.create_store_print_profile(db, tenant_id=tid, store_id=sid, body=body)
    return success(data=dump_model(data), msg="添加成功")


@router.patch("/store-print/profiles/{profile_id}")
def patch_print_profile(
    profile_id: int,
    db: SessionDep,
    body: StorePrintProfilePatchIn,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.patch_store_print_profile(db, store_id=sid, profile_id=profile_id, body=body)
    return success(data=dump_model(data), msg="更新成功")


@router.delete("/store-print/profiles/{profile_id}")
def delete_print_profile(
    profile_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    svc.delete_store_print_profile(db, store_id=sid, profile_id=profile_id)
    return success(msg="已停用")


@router.post("/store-print/profiles/{profile_id}/test")
def test_print_profile(
    profile_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.test_print_profile(db, tenant_id=tid, store_id=sid, profile_id=profile_id)
    return success(data=dump_model(data), msg="测试任务已提交")


@router.get("/store-print/templates")
def list_print_templates(
    scene: Annotated[str | None, Query(description="delivery_sheet / store_retail")] = None,
):
    items = svc.list_print_templates(scene)
    return success(data=items, msg="获取成功")


@router.get("/store-print/scene-settings")
def get_scene_settings(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    items = svc.get_scene_settings(db, store_id=sid)
    return success(data=[dump_model(i) for i in items], msg="获取成功")


@router.put("/store-print/scene-settings")
def put_scene_settings(
    db: SessionDep,
    body: StorePrintSceneSettingsPutIn,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    items = svc.put_scene_settings(db, store_id=sid, settings=body.settings)
    return success(data=[dump_model(i) for i in items], msg="保存成功")


@router.get("/store-print/resolve")
def resolve_print(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
    scene: Annotated[str, Query(description="delivery_sheet / store_retail")] = "delivery_sheet",
    profile_id: Annotated[int | None, Query()] = None,
    template_key: Annotated[str | None, Query()] = None,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.resolve_print_config(
        db, store_id=sid, scene=scene, profile_id=profile_id, template_key=template_key
    )
    return success(data=dump_model(data), msg="获取成功")


@router.post("/store-print/jobs")
def create_print_job(
    db: SessionDep,
    body: StorePrintJobCreateIn,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.create_print_job(
        db, tenant_id=tid, store_id=sid, admin_username=admin_username, body=body
    )
    return success(data=dump_model(data), msg="打印任务已提交")
