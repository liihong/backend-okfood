"""包装品类接口。不改结存。"""

from fastapi import APIRouter, Depends

from app.api.packaging.deps import packaging_store_id
from app.core.deps import SessionDep, admin_staff_subject
from app.models.packaging_stock import PackagingStock
from app.schemas.packaging.sku import PackagingSkuIn, PackagingSkuPatchIn
from app.services.packaging import sku_service
from app.services.packaging.stock_command_service import _sku_initialized
from app.utils.response import success

router = APIRouter(prefix="/skus", tags=["管理端-包装品类"])


@router.get("")
def list_packaging_skus(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    """当前门店的耗材档案。结存在这里只读，修改走库存接口。"""
    _ = admin_username
    rows = []
    for sku in sku_service.list_skus(db, store_id=store_id):
        stock = db.get(PackagingStock, int(sku.id))
        qty = int(stock.qty) if stock is not None else None
        rows.append(
            sku_service.sku_to_dict(
                sku, qty=qty, initialized=_sku_initialized(db, sku.id)
            )
        )
    return success(data=rows, msg="获取成功")


@router.post("")
def create_packaging_sku(
    body: PackagingSkuIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    row = sku_service.create_sku(
        db,
        store_id=store_id,
        name=body.name,
        usage_note=body.usage_note,
        supplier_name=body.supplier_name,
        unit=body.unit,
        safety_stock=body.safety_stock,
        is_meal_bag=body.is_meal_bag,
    )
    return success(
        data=sku_service.sku_to_dict(row, qty=None, initialized=False),
        msg="耗材已保存",
    )


@router.patch("/{sku_id}")
def patch_packaging_sku(
    sku_id: int,
    body: PackagingSkuPatchIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    fields = body.model_fields_set
    row = sku_service.patch_sku(
        db,
        sku_id,
        store_id=store_id,
        name=body.name,
        usage_note=body.usage_note if "usage_note" in fields else None,
        supplier_name=body.supplier_name if "supplier_name" in fields else None,
        unit=body.unit,
        safety_stock=body.safety_stock,
        safety_stock_set="safety_stock" in fields,
        is_active=body.is_active,
        is_meal_bag=body.is_meal_bag,
    )
    stock = db.get(PackagingStock, int(row.id))
    qty = int(stock.qty) if stock is not None else None
    return success(
        data=sku_service.sku_to_dict(row, qty=qty, initialized=_sku_initialized(db, row.id)),
        msg="耗材已保存",
    )


@router.delete("/{sku_id}")
def delete_packaging_sku(
    sku_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    sku_service.delete_sku(db, sku_id, store_id=store_id)
    return success(msg="耗材已删除")


@router.post("/import-defaults")
def import_default_packaging_skus(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    """只补当前门店还没有的常用品，并把「打包袋」标成每餐一只。"""
    _ = admin_username
    created = sku_service.import_default_skus(db, store_id=store_id)
    return success(data={"created": created}, msg="常用耗材已导入")
