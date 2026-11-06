"""后台：会员卡模版（零售商品 CRUD 已拆分至 retail_*_admin_service）。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.membership_card_template import MembershipCardTemplate
from app.schemas.catalog_admin import (
    MembershipCardTemplateCreateIn,
    MembershipCardTemplatePatchIn,
)
from app.services.retail.retail_display import decimal_to_str_money


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


def _validate_card_gifts(
    db: Session,
    *,
    store_id: int,
    gift_dinner_meals: int,
    gift_retail_product_id: int | None,
    gift_retail_quantity: int,
) -> None:
    """一张卡只能赠送晚餐或果蔬汁。果蔬汁必须选本店 SKU，次数就是开卡时的订单笔数。"""
    dinner_n = int(gift_dinner_meals or 0)
    juice_n = int(gift_retail_quantity or 0)
    if dinner_n > 0 and juice_n > 0:
        raise HTTPException(status_code=400, detail="一张会员卡只能赠送晚餐或果蔬汁，不能同时赠送")
    if juice_n > 0 and gift_retail_product_id is None:
        raise HTTPException(status_code=400, detail="赠送果蔬汁请选择 SKU")
    if gift_retail_product_id is not None and juice_n <= 0:
        raise HTTPException(status_code=400, detail="请填写果蔬汁赠送次数")
    if gift_retail_product_id is None:
        return
    from app.models.store_retail_product import StoreRetailProduct

    product = db.get(StoreRetailProduct, int(gift_retail_product_id))
    if product is None or int(product.store_id) != int(store_id):
        raise HTTPException(status_code=400, detail="果蔬汁 SKU 不存在或不属于本店")


def create_membership_template(
    db: Session, *, tenant_id: int, store_id: int, body: MembershipCardTemplateCreateIn
) -> MembershipCardTemplate:
    kl = (body.kind_label or "").strip()
    if not kl:
        raise HTTPException(status_code=400, detail="请填写会员卡种类（如：周卡、季卡）")
    from app.services.meal_period.combo_with_lunch import coerce_deliver_dinner_with_lunch
    from app.services.meal_period.template_periods import normalize_meal_periods_list

    periods = normalize_meal_periods_list(body.meal_periods)
    gift_dinner = int(body.gift_dinner_meals or 0)
    gift_qty = int(body.gift_retail_quantity or 0)
    gift_pid = int(body.gift_retail_product_id) if body.gift_retail_product_id is not None else None
    _validate_card_gifts(
        db,
        store_id=int(store_id),
        gift_dinner_meals=gift_dinner,
        gift_retail_product_id=gift_pid,
        gift_retail_quantity=gift_qty,
    )
    row = MembershipCardTemplate(
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        period_kind=None,
        meal_periods=periods,
        deliver_dinner_with_lunch=coerce_deliver_dinner_with_lunch(
            periods, bool(body.deliver_dinner_with_lunch)
        ),
        kind_label=kl[:64],
        name=body.name.strip(),
        meals_grant=int(body.meals_grant),
        gift_dinner_meals=gift_dinner,
        gift_retail_product_id=gift_pid if gift_qty > 0 else None,
        gift_retail_quantity=gift_qty if gift_pid is not None else 0,
        list_price_yuan=Decimal(body.list_price_yuan) if body.list_price_yuan is not None else None,
        sale_price_yuan=Decimal(body.sale_price_yuan) if body.sale_price_yuan is not None else None,
        card_style_image_url=(body.card_style_image_url.strip() or None) if body.card_style_image_url else None,
        validity_days=int(body.validity_days) if body.validity_days is not None else None,
        intro_short=(body.intro_short.strip() or None) if body.intro_short else None,
        purchase_notice=(body.purchase_notice.strip() or None) if body.purchase_notice else None,
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
    fs = body.model_fields_set
    if "gift_dinner_meals" in fs or "gift_retail_product_id" in fs or "gift_retail_quantity" in fs:
        gift_dinner = (
            int(body.gift_dinner_meals)
            if "gift_dinner_meals" in fs and body.gift_dinner_meals is not None
            else int(getattr(row, "gift_dinner_meals", 0) or 0)
        )
        if "gift_retail_quantity" in fs and body.gift_retail_quantity is not None:
            gift_qty = int(body.gift_retail_quantity)
        else:
            gift_qty = int(getattr(row, "gift_retail_quantity", 0) or 0)
        if "gift_retail_product_id" in fs:
            gift_pid = int(body.gift_retail_product_id) if body.gift_retail_product_id is not None else None
        else:
            raw_pid = getattr(row, "gift_retail_product_id", None)
            gift_pid = int(raw_pid) if raw_pid is not None else None
        _validate_card_gifts(
            db,
            store_id=int(store_id),
            gift_dinner_meals=gift_dinner,
            gift_retail_product_id=gift_pid,
            gift_retail_quantity=gift_qty,
        )
        row.gift_dinner_meals = gift_dinner
        row.gift_retail_quantity = gift_qty if gift_pid is not None else 0
        row.gift_retail_product_id = gift_pid if gift_qty > 0 else None
    if body.remark is not None:
        row.remark = body.remark.strip() or None
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    if body.is_active is not None:
        row.is_active = bool(body.is_active)
    fs = body.model_fields_set
    if "list_price_yuan" in fs:
        row.list_price_yuan = Decimal(body.list_price_yuan) if body.list_price_yuan is not None else None
    if "sale_price_yuan" in fs:
        row.sale_price_yuan = Decimal(body.sale_price_yuan) if body.sale_price_yuan is not None else None
    if "card_style_image_url" in fs:
        row.card_style_image_url = (
            (body.card_style_image_url.strip() or None) if body.card_style_image_url else None
        )
    if "validity_days" in fs:
        row.validity_days = int(body.validity_days) if body.validity_days is not None else None
    if "intro_short" in fs:
        row.intro_short = (body.intro_short.strip() or None) if body.intro_short else None
    if "purchase_notice" in fs:
        row.purchase_notice = (body.purchase_notice.strip() or None) if body.purchase_notice else None
    from app.services.meal_period.combo_with_lunch import coerce_deliver_dinner_with_lunch
    from app.services.meal_period.template_periods import normalize_meal_periods_list

    if body.meal_periods is not None:
        row.meal_periods = normalize_meal_periods_list(body.meal_periods)
    periods_now = normalize_meal_periods_list(getattr(row, "meal_periods", None))
    flag_in = (
        bool(body.deliver_dinner_with_lunch)
        if body.deliver_dinner_with_lunch is not None
        else bool(getattr(row, "deliver_dinner_with_lunch", False))
    )
    # 改成只勾单餐段时强制关掉，避免脏配置跟到新开卡
    row.deliver_dinner_with_lunch = coerce_deliver_dinner_with_lunch(periods_now, flag_in)
    db.commit()
    db.refresh(row)
    return row


def delete_membership_template(db: Session, *, template_id: int, tenant_id: int, store_id: int) -> None:
    row = get_membership_template_row(db, template_id=template_id, tenant_id=tenant_id, store_id=store_id)
    db.delete(row)
    db.commit()


def _fallback_kind_from_period(period_kind: str | None) -> str:
    if period_kind == "weekly":
        return "周卡"
    if period_kind == "monthly":
        return "月卡"
    if period_kind:
        return str(period_kind)
    return "会员卡"


def membership_template_public_dump(row: MembershipCardTemplate) -> dict:
    """会员端列表：不含备注与租户内部字段。"""
    kl = (getattr(row, "kind_label", None) or "").strip()
    if not kl:
        kl = _fallback_kind_from_period(row.period_kind)
    vd = getattr(row, "validity_days", None)
    return {
        "id": int(row.id),
        "kind_label": kl[:64],
        "name": row.name,
        "meals_grant": int(row.meals_grant),
        "list_price_yuan": decimal_to_str_money(getattr(row, "list_price_yuan", None)),
        "sale_price_yuan": decimal_to_str_money(getattr(row, "sale_price_yuan", None)),
        "card_style_image_url": getattr(row, "card_style_image_url", None),
        "validity_days": int(vd) if vd is not None else None,
        "intro_short": getattr(row, "intro_short", None),
        "purchase_notice": getattr(row, "purchase_notice", None),
        "sort_order": int(row.sort_order),
    }


def resolve_membership_template_member_filter(
    db: Session, *, template_id: int, tenant_id: int, store_id: int
) -> tuple[list[int], str | None, tuple[str, ...]]:
    """
    会员档案库按租户卡包筛选：返回同店「种类 + 餐段」相同的模版 id，
    以及无卡包工单时按计费周期 + 餐段兜底（只读匹配，不改档案）。
    """
    from app.services.meal_period.template_periods import (
        catalog_periods_from_template,
        meal_periods_from_template,
    )
    from app.services.member.member_card_order_service import _plan_for_membership_template

    row = get_membership_template_row(
        db, template_id=int(template_id), tenant_id=int(tenant_id), store_id=int(store_id)
    )
    want_kind = (row.kind_label or "").strip()
    want_periods = tuple(meal_periods_from_template(row))
    ids: list[int] = []
    for t in list_membership_templates(
        db, tenant_id=int(row.tenant_id), store_id=int(row.store_id), active_only=False
    ):
        if (t.kind_label or "").strip() != want_kind:
            continue
        if tuple(meal_periods_from_template(t)) != want_periods:
            continue
        ids.append(int(t.id))
    if int(row.id) not in ids:
        ids.append(int(row.id))
    fallback = _plan_for_membership_template(row).value
    # 筛选用卡包文案餐段，避免「晚餐」库内勾了午餐后与「午餐+晚餐」混筛
    return ids, fallback, tuple(catalog_periods_from_template(row))


def membership_template_dump(row: MembershipCardTemplate) -> dict:
    from app.services.meal_period.template_periods import normalize_meal_periods_list

    kl = (getattr(row, "kind_label", None) or "").strip()
    if not kl:
        kl = _fallback_kind_from_period(row.period_kind)
    return {
        "id": int(row.id),
        "tenant_id": int(row.tenant_id),
        "kind_label": kl[:64],
        "period_kind": row.period_kind,
        "meal_periods": normalize_meal_periods_list(getattr(row, "meal_periods", None)),
        "deliver_dinner_with_lunch": bool(getattr(row, "deliver_dinner_with_lunch", False)),
        "name": row.name,
        "meals_grant": int(row.meals_grant),
        "gift_dinner_meals": int(getattr(row, "gift_dinner_meals", 0) or 0),
        "gift_retail_product_id": (
            int(row.gift_retail_product_id) if getattr(row, "gift_retail_product_id", None) is not None else None
        ),
        "gift_retail_quantity": int(getattr(row, "gift_retail_quantity", 0) or 0),
        "list_price_yuan": decimal_to_str_money(getattr(row, "list_price_yuan", None)),
        "sale_price_yuan": decimal_to_str_money(getattr(row, "sale_price_yuan", None)),
        "card_style_image_url": getattr(row, "card_style_image_url", None),
        "validity_days": int(row.validity_days) if getattr(row, "validity_days", None) is not None else None,
        "intro_short": getattr(row, "intro_short", None),
        "purchase_notice": getattr(row, "purchase_notice", None),
        "remark": row.remark,
        "sort_order": int(row.sort_order),
        "is_active": bool(row.is_active),
    }

