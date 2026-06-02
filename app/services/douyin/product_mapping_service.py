"""抖音商品映射：管理端 CRUD 与验券时匹配。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.douyin.product_mapping import DouyinProductMapping
from app.models.enums import DouyinGrantType
from app.models.marketing_coupon_template import MarketingCouponTemplate
from app.models.membership_card_template import MembershipCardTemplate
from app.schemas.douyin import (
    DouyinProductMappingCreateIn,
    DouyinProductMappingOut,
    DouyinProductMappingPatchIn,
)
from app.integrations.douyin_life import DouyinPrepareCertificate


def _s(raw: str | None) -> str | None:
    if raw is None:
        return None
    t = str(raw).strip()
    return t or None


def _mapping_to_out(row: DouyinProductMapping) -> DouyinProductMappingOut:
    return DouyinProductMappingOut(
        id=int(row.id),
        display_name=str(row.display_name),
        douyin_product_id=row.douyin_product_id,
        douyin_sku_id=row.douyin_sku_id,
        douyin_product_out_id=row.douyin_product_out_id,
        grant_type=str(row.grant_type),
        target_id=int(row.target_id) if row.target_id is not None else None,
        is_active=bool(row.is_active),
        created_by=str(row.created_by or ""),
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def _cert_id_set(cert: DouyinPrepareCertificate) -> set[str]:
    vals = {
        cert.product_id,
        cert.sku_id,
        cert.product_out_id,
        cert.sku_out_id,
        cert.third_sku_id,
    }
    return {v for v in vals if v}


def find_active_mapping_for_certificate(
    db: Session,
    *,
    store_id: int,
    cert: DouyinPrepareCertificate,
) -> DouyinProductMapping:
    """按验券准备返回的 sku 信息匹配门店映射。"""
    ids = _cert_id_set(cert)
    if not ids:
        raise HTTPException(status_code=400, detail="抖音券未返回可识别的商品信息，请联系管理员配置映射")

    filters = []
    for val in ids:
        filters.extend(
            [
                DouyinProductMapping.douyin_product_id == val,
                DouyinProductMapping.douyin_sku_id == val,
                DouyinProductMapping.douyin_product_out_id == val,
            ]
        )

    row = db.scalar(
        select(DouyinProductMapping)
        .where(
            DouyinProductMapping.store_id == int(store_id),
            DouyinProductMapping.is_active.is_(True),
            or_(*filters),
        )
        .order_by(DouyinProductMapping.id.desc())
        .limit(1)
    )
    if not row:
        raise HTTPException(
            status_code=400,
            detail="该抖音商品尚未配置本地权益映射，请联系管理员",
        )
    return row


def list_douyin_product_mappings_paged(
    db: Session,
    *,
    store_id: int,
    page: int,
    page_size: int,
    keyword: str | None = None,
    active_only: bool = False,
) -> tuple[list[DouyinProductMappingOut], int]:
    q = select(DouyinProductMapping).where(DouyinProductMapping.store_id == int(store_id))
    if active_only:
        q = q.where(DouyinProductMapping.is_active.is_(True))
    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        q = q.where(
            or_(
                DouyinProductMapping.display_name.like(like),
                DouyinProductMapping.douyin_product_id.like(like),
                DouyinProductMapping.douyin_sku_id.like(like),
                DouyinProductMapping.douyin_product_out_id.like(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(DouyinProductMapping.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [_mapping_to_out(r) for r in rows], int(total)


def _validate_grant_target(
    db: Session,
    *,
    store_id: int,
    grant_type: str,
    target_id: int | None,
) -> None:
    """校验映射目标在本门店存在且可用。"""
    gt = DouyinGrantType(str(grant_type))
    if gt in (DouyinGrantType.WEEK_CARD, DouyinGrantType.MONTH_CARD):
        if target_id is not None:
            raise HTTPException(status_code=400, detail="周卡/月卡映射无需 target_id")
        return
    if target_id is None:
        raise HTTPException(status_code=400, detail="卡包或优惠券映射须选择关联目标")
    if gt == DouyinGrantType.COUPON_TEMPLATE:
        tpl = db.get(MarketingCouponTemplate, int(target_id))
        if not tpl or int(tpl.store_id) != int(store_id):
            raise HTTPException(status_code=400, detail="优惠券券种不存在或不属于当前门店")
        if not bool(tpl.is_active):
            raise HTTPException(status_code=400, detail="优惠券券种已下架，不可关联")
        return
    if gt == DouyinGrantType.MEMBERSHIP_TEMPLATE:
        tpl = db.get(MembershipCardTemplate, int(target_id))
        if not tpl or int(tpl.store_id) != int(store_id):
            raise HTTPException(status_code=400, detail="会员卡包不存在或不属于当前门店")
        if not bool(tpl.is_active):
            raise HTTPException(status_code=400, detail="会员卡包已下架，不可关联")
        return
    raise HTTPException(status_code=400, detail="未知映射类型")


def create_douyin_product_mapping(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    body: DouyinProductMappingCreateIn,
    operator: str,
) -> DouyinProductMappingOut:
    tid = int(body.target_id) if body.target_id is not None else None
    _validate_grant_target(
        db, store_id=int(store_id), grant_type=body.grant_type.value, target_id=tid
    )
    row = DouyinProductMapping(
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        display_name=body.display_name.strip(),
        douyin_product_id=_s(body.douyin_product_id),
        douyin_sku_id=_s(body.douyin_sku_id),
        douyin_product_out_id=_s(body.douyin_product_out_id),
        grant_type=body.grant_type.value,
        target_id=tid,
        is_active=bool(body.is_active),
        created_by=operator,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _mapping_to_out(row)


def patch_douyin_product_mapping(
    db: Session,
    *,
    mapping_id: int,
    store_id: int,
    body: DouyinProductMappingPatchIn,
) -> DouyinProductMappingOut:
    row = db.get(DouyinProductMapping, int(mapping_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="映射不存在")
    fs = body.model_fields_set
    if "display_name" in fs and body.display_name is not None:
        row.display_name = body.display_name.strip()
    if "douyin_product_id" in fs:
        row.douyin_product_id = _s(body.douyin_product_id)
    if "douyin_sku_id" in fs:
        row.douyin_sku_id = _s(body.douyin_sku_id)
    if "douyin_product_out_id" in fs:
        row.douyin_product_out_id = _s(body.douyin_product_out_id)
    if "grant_type" in fs and body.grant_type is not None:
        row.grant_type = body.grant_type.value
    if "target_id" in fs:
        row.target_id = int(body.target_id) if body.target_id is not None else None
    if "is_active" in fs and body.is_active is not None:
        row.is_active = bool(body.is_active)

    keys = [
        _s(row.douyin_product_id),
        _s(row.douyin_sku_id),
        _s(row.douyin_product_out_id),
    ]
    if not any(keys):
        raise HTTPException(status_code=400, detail="至少保留一个抖音商品标识")
    gt = DouyinGrantType(str(row.grant_type))
    if gt in (DouyinGrantType.MEMBERSHIP_TEMPLATE, DouyinGrantType.COUPON_TEMPLATE):
        if row.target_id is None:
            raise HTTPException(status_code=400, detail="卡包或优惠券映射须指定 target_id")
    _validate_grant_target(
        db,
        store_id=int(store_id),
        grant_type=str(row.grant_type),
        target_id=int(row.target_id) if row.target_id is not None else None,
    )

    db.commit()
    db.refresh(row)
    return _mapping_to_out(row)


def grant_type_label(grant_type: str, *, display_name: str | None = None) -> str:
    gt = (grant_type or "").strip()
    if gt == DouyinGrantType.WEEK_CARD.value:
        return "周卡"
    if gt == DouyinGrantType.MONTH_CARD.value:
        return "月卡"
    if gt == DouyinGrantType.MEMBERSHIP_TEMPLATE.value:
        return display_name or "会员卡包"
    if gt == DouyinGrantType.COUPON_TEMPLATE.value:
        return display_name or "优惠券"
    return display_name or gt
