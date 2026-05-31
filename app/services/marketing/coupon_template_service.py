"""营销优惠券券种模板 CRUD（配置层）。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.marketing_coupon_template import MarketingCouponTemplate
from app.schemas.marketing.coupon import CouponTemplateCreateIn, CouponTemplateOut, CouponTemplatePatchIn
from app.services.marketing.coupon_checkout_service import format_amount_yuan, validate_scope_target_belongs_store


def _template_to_out(row: MarketingCouponTemplate) -> CouponTemplateOut:
    return CouponTemplateOut(
        id=int(row.id),
        name=str(row.name),
        coupon_type=str(row.coupon_type),
        discount_yuan=format_amount_yuan(Decimal(row.discount_yuan)),
        min_order_yuan=format_amount_yuan(Decimal(row.min_order_yuan or 0)),
        biz_type=str(row.biz_type),
        scope_level=str(row.scope_level),
        scope_target_id=int(row.scope_target_id) if row.scope_target_id is not None else None,
        validity_mode=str(row.validity_mode),
        valid_from=row.valid_from.isoformat() if row.valid_from else None,
        valid_until=row.valid_until.isoformat() if row.valid_until else None,
        valid_days_after_grant=int(row.valid_days_after_grant) if row.valid_days_after_grant is not None else None,
        usage_instructions=(row.usage_instructions or "").strip() or None,
        sort_order=int(row.sort_order or 0),
        is_active=bool(row.is_active),
        max_grants=int(row.max_grants) if row.max_grants is not None else None,
        grants_issued=int(row.grants_issued or 0),
        created_by=str(row.created_by),
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def list_coupon_templates_paged(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    page: int = 1,
    page_size: int = 20,
    biz_type: str | None = None,
    active_only: bool = False,
    keyword: str | None = None,
) -> tuple[list[CouponTemplateOut], int]:
    q = select(MarketingCouponTemplate).where(
        MarketingCouponTemplate.tenant_id == int(tenant_id),
        MarketingCouponTemplate.store_id == int(store_id),
    )
    if biz_type:
        q = q.where(MarketingCouponTemplate.biz_type == biz_type.strip())
    if active_only:
        q = q.where(MarketingCouponTemplate.is_active.is_(True))
    kw = (keyword or "").strip()
    if kw:
        q = q.where(MarketingCouponTemplate.name.contains(kw))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(MarketingCouponTemplate.sort_order.desc(), MarketingCouponTemplate.id.desc())
        .offset(max(0, (page - 1) * page_size))
        .limit(page_size)
    ).all()
    return [_template_to_out(r) for r in rows], int(total)


def create_coupon_template(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    body: CouponTemplateCreateIn,
    operator: str,
) -> CouponTemplateOut:
    validate_scope_target_belongs_store(
        db,
        store_id=int(store_id),
        biz_type=body.biz_type.value,
        scope_level=body.scope_level.value,
        scope_target_id=body.scope_target_id,
    )
    row = MarketingCouponTemplate(
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        name=body.name.strip(),
        coupon_type=body.coupon_type.value,
        discount_yuan=Decimal(body.discount_yuan),
        min_order_yuan=Decimal(body.min_order_yuan),
        biz_type=body.biz_type.value,
        scope_level=body.scope_level.value,
        scope_target_id=int(body.scope_target_id) if body.scope_target_id is not None else None,
        validity_mode=body.validity_mode.value,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        valid_days_after_grant=body.valid_days_after_grant,
        usage_instructions=body.usage_instructions,
        sort_order=int(body.sort_order),
        is_active=bool(body.is_active),
        max_grants=int(body.max_grants) if body.max_grants is not None else None,
        grants_issued=0,
        created_by=(operator or "").strip()[:64] or "admin",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _template_to_out(row)


def patch_coupon_template(
    db: Session,
    *,
    template_id: int,
    store_id: int,
    body: CouponTemplatePatchIn,
) -> CouponTemplateOut:
    row = db.get(MarketingCouponTemplate, int(template_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="券种不存在")
    data = body.model_dump(exclude_unset=True)
    if not data:
        return _template_to_out(row)
    if "name" in data and data["name"] is not None:
        row.name = str(data["name"]).strip()
    if "discount_yuan" in data and data["discount_yuan"] is not None:
        row.discount_yuan = Decimal(data["discount_yuan"])
    if "min_order_yuan" in data and data["min_order_yuan"] is not None:
        row.min_order_yuan = Decimal(data["min_order_yuan"])
    if "biz_type" in data and data["biz_type"] is not None:
        row.biz_type = data["biz_type"].value if hasattr(data["biz_type"], "value") else str(data["biz_type"])
    if "scope_level" in data and data["scope_level"] is not None:
        row.scope_level = (
            data["scope_level"].value if hasattr(data["scope_level"], "value") else str(data["scope_level"])
        )
    if "scope_target_id" in data:
        row.scope_target_id = int(data["scope_target_id"]) if data["scope_target_id"] is not None else None
    if "validity_mode" in data and data["validity_mode"] is not None:
        row.validity_mode = (
            data["validity_mode"].value if hasattr(data["validity_mode"], "value") else str(data["validity_mode"])
        )
    if "valid_from" in data:
        row.valid_from = data["valid_from"]
    if "valid_until" in data:
        row.valid_until = data["valid_until"]
    if "valid_days_after_grant" in data:
        row.valid_days_after_grant = data["valid_days_after_grant"]
    if "usage_instructions" in data:
        row.usage_instructions = data["usage_instructions"]
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = int(data["sort_order"])
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
    if "max_grants" in data:
        row.max_grants = int(data["max_grants"]) if data["max_grants"] is not None else None

    validate_scope_target_belongs_store(
        db,
        store_id=int(store_id),
        biz_type=str(row.biz_type),
        scope_level=str(row.scope_level),
        scope_target_id=int(row.scope_target_id) if row.scope_target_id is not None else None,
    )
    db.commit()
    db.refresh(row)
    return _template_to_out(row)


def set_coupon_template_active(
    db: Session, *, template_id: int, store_id: int, is_active: bool
) -> CouponTemplateOut:
    row = db.get(MarketingCouponTemplate, int(template_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="券种不存在")
    row.is_active = bool(is_active)
    db.commit()
    db.refresh(row)
    return _template_to_out(row)


def get_coupon_template_row(db: Session, *, template_id: int, store_id: int) -> MarketingCouponTemplate:
    row = db.get(MarketingCouponTemplate, int(template_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="券种不存在")
    return row
