"""采购资料接口。只读写备忘，不碰库存和菜品。"""

from fastapi import APIRouter, Depends, Query

from app.api.packaging.deps import packaging_store_id
from app.core.deps import SessionDep, admin_staff_subject
from app.schemas.packaging.purchase_note import PurchaseNoteIn, PurchaseNotePatchIn
from app.services.packaging import purchase_note_service
from app.utils.response import success

router = APIRouter(prefix="/purchase-notes", tags=["管理端-采购资料"])


@router.get("")
def list_purchase_notes(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
    q: str | None = Query(None, description="名称、联系方式、平台或备注"),
    category: str | None = Query(None, description="ingredient 或 consumable"),
    record_method: str | None = Query(None, description="link、wechat、phone 或 other"),
):
    _ = admin_username
    rows = purchase_note_service.list_notes(
        db,
        store_id=store_id,
        q=q,
        category=category,
        record_method=record_method,
    )
    return success(
        data=[purchase_note_service.note_to_dict(row) for row in rows],
        msg="获取成功",
    )


@router.post("")
def create_purchase_note(
    body: PurchaseNoteIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    row = purchase_note_service.create_note(
        db,
        store_id=store_id,
        category=body.category,
        name=body.name,
        record_method=body.record_method,
        contact_value=body.contact_value,
        platform=body.platform,
        supplier_label=body.supplier_label,
        remark=body.remark,
    )
    return success(data=purchase_note_service.note_to_dict(row), msg="采购资料已保存")


@router.patch("/{note_id}")
def patch_purchase_note(
    note_id: int,
    body: PurchaseNotePatchIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    fields = body.model_fields_set
    row = purchase_note_service.patch_note(
        db,
        note_id,
        store_id=store_id,
        category=body.category,
        name=body.name,
        record_method=body.record_method,
        contact_value=body.contact_value,
        platform=body.platform,
        platform_set="platform" in fields,
        supplier_label=body.supplier_label,
        supplier_label_set="supplier_label" in fields,
        remark=body.remark,
        remark_set="remark" in fields,
    )
    return success(data=purchase_note_service.note_to_dict(row), msg="采购资料已保存")


@router.delete("/{note_id}")
def delete_purchase_note(
    note_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    purchase_note_service.delete_note(db, note_id, store_id=store_id)
    return success(msg="采购资料已删除")
