"""后台：会员卡模版 + 门店零售 SKU（仅 CRUD；不接支付入账与配送）。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.membership_card_template import MembershipCardTemplate
from app.models.store import Store
from app.models.store_retail_category import StoreRetailCategory
from app.models.store_retail_product import StoreRetailProduct
from app.schemas.catalog_admin import (
    MembershipCardTemplateCreateIn,
    MembershipCardTemplatePatchIn,
    StoreRetailCategoryCreateIn,
    StoreRetailCategoryPatchIn,
    StoreRetailProductCreateIn,
    StoreRetailProductPatchIn,
)



def assert_retail_category_belongs_store(db: Session, *, category_id: int, store_id: int) -> StoreRetailCategory:
    c = db.get(StoreRetailCategory, category_id)
    if not c or int(c.store_id) != store_id:
        raise HTTPException(status_code=404, detail="零售分类不存在或所属门店不匹配")
    return c


def list_membership_templates(
    db: Session, *, tenant_id: int, store_id: int, active_only: bool = False
) -> list[MembershipCardTemplate]:
    q = (
        select(MembershipCardTemplate)
        .where(MembershipCardTemplate.tenant_id == int(tenant_id), MembershipCardTemplate.store_id == int(store_id))
        .order_by(MembershipCardTemplate.sort_order.asc(), MembershipCardTemplate.id.asc())
    )
    if active_only:
        q = q.where(MembershipCardTemplate.is_active.is_(True))
    return list(db.scalars(q).all())


def create_membership_template(
    db: Session, *, tenant_id: int, store_id: int, body: MembershipCardTemplateCreateIn
) -> MembershipCardTemplate:
    kl = (body.kind_label or "").strip()
    if not kl:
        raise HTTPException(status_code=400, detail="请填写会员卡种类（如：周卡、季卡）")
    row = MembershipCardTemplate(
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        period_kind=None,
        kind_label=kl[:64],
        name=body.name.strip(),
        meals_grant=int(body.meals_grant),
        remark=(body.remark.strip() if body.remark else None),
        sort_order=int(body.sort_order),
        is_active=bool(body.is_active),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_membership_template_row(
    db: Session, *, template_id: int, tenant_id: int, store_id: int
) -> MembershipCardTemplate:
    row = db.get(MembershipCardTemplate, template_id)
    if not row or int(row.store_id) != int(store_id) or int(row.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="会员卡模版不存在")
    return row


def patch_membership_template(
    db: Session,
    *,
    template_id: int,
    tenant_id: int,
    store_id: int,
    body: MembershipCardTemplatePatchIn,
) -> MembershipCardTemplate:
    row = get_membership_template_row(db, template_id=template_id, tenant_id=tenant_id, store_id=store_id)
    if body.kind_label is not None:
        k = body.kind_label.strip()
        if not k:
            raise HTTPException(status_code=400, detail="种类不能为空")
        row.kind_label = k[:64]
    if body.name is not None:
        row.name = body.name.strip()
    if body.meals_grant is not None:
        row.meals_grant = int(body.meals_grant)
    if body.remark is not None:
        row.remark = body.remark.strip() or None
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    if body.is_active is not None:
        row.is_active = bool(body.is_active)
    db.commit()
    db.refresh(row)
    return row


def delete_membership_template(db: Session, *, template_id: int, tenant_id: int, store_id: int) -> None:
    row = get_membership_template_row(db, template_id=template_id, tenant_id=tenant_id, store_id=store_id)
    db.delete(row)
    db.commit()


def list_retail_categories(db: Session, *, store_id: int, active_only: bool = False) -> list[StoreRetailCategory]:
    q = select(StoreRetailCategory).where(StoreRetailCategory.store_id == int(store_id)).order_by(
        StoreRetailCategory.sort_order.asc(), StoreRetailCategory.id.asc()
    )
    if active_only:
        q = q.where(StoreRetailCategory.is_active.is_(True))
    return list(db.scalars(q).all())


def create_retail_category(
    db: Session, *, store_id: int, body: StoreRetailCategoryCreateIn
) -> StoreRetailCategory:
    st = db.get(Store, store_id)
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    row = StoreRetailCategory(
        store_id=int(store_id),
        name=body.name.strip(),
        sort_order=int(body.sort_order),
        is_active=bool(body.is_active),
    )
    db.add(row)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        if _is_mysql_dup(e):
            raise HTTPException(status_code=400, detail="该门店下已有同名分类")
        raise
    db.refresh(row)
    return row


def patch_retail_category(
    db: Session, *, category_id: int, store_id: int, body: StoreRetailCategoryPatchIn
) -> StoreRetailCategory:
    row = assert_retail_category_belongs_store(db, category_id=category_id, store_id=store_id)
    if body.name is not None:
        row.name = body.name.strip()
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    if body.is_active is not None:
        row.is_active = bool(body.is_active)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        if _is_mysql_dup(e):
            raise HTTPException(status_code=400, detail="该门店下已有同名分类")
        raise
    db.refresh(row)
    return row


def delete_retail_category(db: Session, *, category_id: int, store_id: int) -> None:
    row = assert_retail_category_belongs_store(db, category_id=category_id, store_id=store_id)
    cnt = db.scalar(
        select(func.count()).select_from(StoreRetailProduct).where(StoreRetailProduct.category_id == int(category_id))
    )
    if int(cnt or 0) > 0:
        raise HTTPException(status_code=400, detail="该分类下仍有商品，无法删除")

    db.delete(row)
    db.commit()


def _is_mysql_dup(e: Exception) -> bool:
    s = str(e).lower()
    return "duplicate" in s or "1062" in s


def list_retail_products(
    db: Session, *, store_id: int, category_id: int | None = None, shelf_only: bool = False
) -> list[StoreRetailProduct]:
    q = (
        select(StoreRetailProduct)
        .where(StoreRetailProduct.store_id == int(store_id))
        .order_by(StoreRetailProduct.sort_order.asc(), StoreRetailProduct.id.asc())
    )
    if category_id is not None:
        q = q.where(StoreRetailProduct.category_id == int(category_id))
    if shelf_only:
        q = q.where(StoreRetailProduct.is_on_shelf.is_(True))
    return list(db.scalars(q).all())


def create_retail_product(db: Session, *, store_id: int, body: StoreRetailProductCreateIn) -> StoreRetailProduct:
    st = db.get(Store, store_id)
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    cid = body.category_id
    if cid is not None:
        assert_retail_category_belongs_store(db, category_id=int(cid), store_id=store_id)
    row = StoreRetailProduct(
        store_id=int(store_id),
        category_id=int(cid) if cid is not None else None,
        sku_code=(body.sku_code.strip() or None) if body.sku_code else None,
        title=body.title.strip(),
        subtitle=(body.subtitle.strip() if body.subtitle else None),
        description=body.description,
        unit_price_yuan=Decimal(body.unit_price_yuan),
        list_price_yuan=Decimal(body.list_price_yuan) if body.list_price_yuan is not None else None,
        cover_image_url=(body.cover_image_url.strip() or None) if body.cover_image_url else None,
        sort_order=int(body.sort_order),
        is_on_shelf=bool(body.is_on_shelf),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_retail_product_row(db: Session, *, product_id: int, store_id: int) -> StoreRetailProduct:
    row = db.get(StoreRetailProduct, product_id)
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="商品不存在")
    return row


def patch_retail_product(
    db: Session, *, product_id: int, store_id: int, body: StoreRetailProductPatchIn
) -> StoreRetailProduct:
    row = get_retail_product_row(db, product_id=product_id, store_id=store_id)
    raw = body.model_dump(exclude_unset=True)
    if "category_id" in raw:
        v = raw["category_id"]
        if v is None:
            row.category_id = None
        else:
            assert_retail_category_belongs_store(db, category_id=int(v), store_id=store_id)
            row.category_id = int(v)
    if body.sku_code is not None:
        row.sku_code = body.sku_code.strip() or None
    if body.title is not None:
        row.title = body.title.strip()
    if body.subtitle is not None:
        row.subtitle = body.subtitle.strip() or None
    if body.description is not None:
        row.description = body.description
    if body.unit_price_yuan is not None:
        row.unit_price_yuan = Decimal(body.unit_price_yuan)
    if body.list_price_yuan is not None:
        row.list_price_yuan = Decimal(body.list_price_yuan) if body.list_price_yuan else None
    if body.cover_image_url is not None:
        row.cover_image_url = body.cover_image_url.strip() or None
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    if body.is_on_shelf is not None:
        row.is_on_shelf = bool(body.is_on_shelf)
    db.commit()
    db.refresh(row)
    return row


def delete_retail_product(db: Session, *, product_id: int, store_id: int) -> None:
    row = get_retail_product_row(db, product_id=product_id, store_id=store_id)
    db.delete(row)
    db.commit()


def decimal_to_str_money(v: Decimal | None) -> str | None:
    if v is None:
        return None
    return format(Decimal(v), "f")


def _fallback_kind_from_period(period_kind: str | None) -> str:
    if period_kind == "weekly":
        return "周卡"
    if period_kind == "monthly":
        return "月卡"
    if period_kind:
        return str(period_kind)
    return "会员卡"


def membership_template_dump(row: MembershipCardTemplate) -> dict:
    kl = (getattr(row, "kind_label", None) or "").strip()
    if not kl:
        kl = _fallback_kind_from_period(row.period_kind)
    return {
        "id": int(row.id),
        "store_id": int(row.store_id),
        "tenant_id": int(row.tenant_id),
        "kind_label": kl[:64],
        "period_kind": row.period_kind,
        "name": row.name,
        "meals_grant": int(row.meals_grant),
        "remark": row.remark,
        "sort_order": int(row.sort_order),
        "is_active": bool(row.is_active),
    }


def retail_product_dump(row: StoreRetailProduct) -> dict:
    return {
        "id": int(row.id),
        "store_id": int(row.store_id),
        "category_id": int(row.category_id) if row.category_id is not None else None,
        "sku_code": row.sku_code,
        "title": row.title,
        "subtitle": row.subtitle,
        "description": row.description,
        "unit_price_yuan": decimal_to_str_money(row.unit_price_yuan),
        "list_price_yuan": decimal_to_str_money(row.list_price_yuan),
        "cover_image_url": row.cover_image_url,
        "sort_order": int(row.sort_order),
        "is_on_shelf": bool(row.is_on_shelf),
    }
