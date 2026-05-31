"""营销优惠券：金额计算、发放、锁券与购卡集成测试。"""

from __future__ import annotations

from decimal import Decimal

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive

from app.models.enums import (
    CouponBizType,
    CouponLockedOrderBiz,
    CouponScopeLevel,
    CouponType,
    CouponValidityMode,
)
from app.models.member_coupon import MemberCoupon
from app.schemas.marketing.coupon import CouponTemplateCreateIn, MemberCouponBatchGrantIn, MemberCouponGrantIn
from app.services.marketing.coupon_checkout_service import compute_coupon_payable, release_member_coupon_for_order
from app.services.marketing.coupon_template_service import create_coupon_template
from app.services.marketing.member_coupon_service import grant_member_coupon, grant_member_coupons_batch, list_member_card_coupons_for_reminder
from app.services.member_card_pay_service import (
    apply_member_coupon_to_unpaid_card_order,
    create_miniprogram_member_card_order,
    expire_stale_unpaid_miniprogram_card_orders,
)


def test_compute_coupon_payable_caps_at_min_pay():
    payable, disc = compute_coupon_payable(Decimal("50"), Decimal("100"))
    assert payable == Decimal("0.01")
    assert disc == Decimal("49.99")


def test_grant_and_lock_member_card_coupon(db: Session, new_member, mall_template) -> None:
    body = CouponTemplateCreateIn(
        name="卡包减50",
        coupon_type=CouponType.CASH,
        discount_yuan=Decimal("50"),
        min_order_yuan=Decimal("0"),
        biz_type=CouponBizType.MEMBER_CARD,
        scope_level=CouponScopeLevel.MEMBERSHIP_TEMPLATE,
        scope_target_id=int(mall_template.id),
        validity_mode=CouponValidityMode.DAYS_AFTER_GRANT,
        valid_days_after_grant=30,
    )
    tpl = create_coupon_template(db, tenant_id=1, store_id=1, body=body, operator="admin")
    granted = grant_member_coupon(
        db,
        tenant_id=1,
        store_id=1,
        body=MemberCouponGrantIn(template_id=tpl.id, member_phone=str(new_member.phone)),
        operator="admin",
    )
    order = create_miniprogram_member_card_order(
        db,
        int(new_member.id),
        membership_template_id=int(mall_template.id),
        member_coupon_id=granted.id,
    )
    assert order.original_amount_yuan == Decimal("188.00")
    assert order.coupon_discount_yuan == Decimal("50.00")
    assert order.amount_yuan == Decimal("138.00")
    assert "优惠券" in (order.remark or "")
    assert "卡包减50" in (order.remark or "")
    assert "减50.00元" in (order.remark or "")
    assert "用户券#" in (order.remark or "")
    mc = db.get(MemberCoupon, granted.id)
    assert mc is not None
    assert mc.status == "locked"
    release_member_coupon_for_order(
        db, order_biz=CouponLockedOrderBiz.MEMBER_CARD, order_id=int(order.id)
    )
    db.commit()
    db.refresh(mc)
    assert mc.status == "available"


def test_create_order_without_coupon_unchanged(db: Session, new_member, mall_template) -> None:
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    assert order.member_coupon_id is None
    assert order.original_amount_yuan is None
    assert order.amount_yuan == Decimal("188.00")


def test_apply_coupon_to_pending_card_order(db: Session, new_member, mall_template) -> None:
    """409 续付场景：对已有未支付单应用优惠券。"""
    pending = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    body = CouponTemplateCreateIn(
        name="续付减30",
        coupon_type=CouponType.CASH,
        discount_yuan=Decimal("30"),
        min_order_yuan=Decimal("0"),
        biz_type=CouponBizType.MEMBER_CARD,
        scope_level=CouponScopeLevel.MEMBERSHIP_TEMPLATE,
        scope_target_id=int(mall_template.id),
        validity_mode=CouponValidityMode.DAYS_AFTER_GRANT,
        valid_days_after_grant=30,
    )
    tpl = create_coupon_template(db, tenant_id=1, store_id=1, body=body, operator="admin")
    granted = grant_member_coupon(
        db,
        tenant_id=1,
        store_id=1,
        body=MemberCouponGrantIn(template_id=tpl.id, member_phone=str(new_member.phone)),
        operator="admin",
    )
    updated = apply_member_coupon_to_unpaid_card_order(
        db, int(new_member.id), int(pending.id), int(granted.id)
    )
    assert int(updated.id) == int(pending.id)
    assert updated.amount_yuan == Decimal("158.00")
    assert updated.member_coupon_id == granted.id
    assert "优惠券" in (updated.remark or "")
    assert "续付减30" in (updated.remark or "")


def test_expire_stale_unpaid_card_order_releases_coupon(db: Session, new_member, mall_template) -> None:
    body = CouponTemplateCreateIn(
        name="超时释放",
        coupon_type=CouponType.CASH,
        discount_yuan=Decimal("10"),
        min_order_yuan=Decimal("0"),
        biz_type=CouponBizType.MEMBER_CARD,
        scope_level=CouponScopeLevel.ALL,
        validity_mode=CouponValidityMode.DAYS_AFTER_GRANT,
        valid_days_after_grant=30,
    )
    tpl = create_coupon_template(db, tenant_id=1, store_id=1, body=body, operator="admin")
    granted = grant_member_coupon(
        db,
        tenant_id=1,
        store_id=1,
        body=MemberCouponGrantIn(template_id=tpl.id, member_phone=str(new_member.phone)),
        operator="admin",
    )
    order = create_miniprogram_member_card_order(
        db,
        int(new_member.id),
        membership_template_id=int(mall_template.id),
        member_coupon_id=granted.id,
    )
    assert order.member_coupon_id == granted.id
    stale_time = beijing_now_naive() - timedelta(minutes=31)
    order.created_at = stale_time
    order.updated_at = stale_time
    db.commit()
    n = expire_stale_unpaid_miniprogram_card_orders(db, member_id=int(new_member.id))
    assert n == 1
    db.refresh(order)
    db.refresh(db.get(MemberCoupon, granted.id))
    mc = db.get(MemberCoupon, granted.id)
    assert mc is not None
    assert mc.status == "available"
    assert order.member_coupon_id is None
    assert order.amount_yuan == Decimal("188.00")
    assert "优惠券" not in (order.remark or "")


def test_grant_member_coupon_by_phone_and_batch(db: Session, new_member, mall_template) -> None:
    body = CouponTemplateCreateIn(
        name="批量减5",
        coupon_type=CouponType.CASH,
        discount_yuan=Decimal("5"),
        min_order_yuan=Decimal("0"),
        biz_type=CouponBizType.MEMBER_CARD,
        scope_level=CouponScopeLevel.ALL,
        validity_mode=CouponValidityMode.DAYS_AFTER_GRANT,
        valid_days_after_grant=30,
        max_grants=10,
    )
    tpl = create_coupon_template(db, tenant_id=1, store_id=1, body=body, operator="admin")
    granted = grant_member_coupon(
        db,
        tenant_id=1,
        store_id=1,
        body=MemberCouponGrantIn(template_id=tpl.id, member_phone=str(new_member.phone)),
        operator="admin",
    )
    assert granted.member_phone == str(new_member.phone)

    batch = grant_member_coupons_batch(
        db,
        tenant_id=1,
        store_id=1,
        body=MemberCouponBatchGrantIn(
            template_id=tpl.id,
            member_phones=[str(new_member.phone), "19900000000", "19900000000"],
        ),
        operator="admin",
    )
    assert batch.success_count == 1
    assert len(batch.failed) == 1
    assert batch.failed[0].member_phone == "19900000000"


def test_member_card_coupon_reminder_includes_available(db: Session, new_member, mall_template) -> None:
    """进小程序提醒：购卡券存在且不做 scope 预筛。"""
    body = CouponTemplateCreateIn(
        name="提醒测试券",
        coupon_type=CouponType.CASH,
        discount_yuan=Decimal("10"),
        min_order_yuan=Decimal("0"),
        biz_type=CouponBizType.MEMBER_CARD,
        scope_level=CouponScopeLevel.MEMBERSHIP_TEMPLATE,
        scope_target_id=int(mall_template.id),
        validity_mode=CouponValidityMode.DAYS_AFTER_GRANT,
        valid_days_after_grant=30,
    )
    tpl = create_coupon_template(db, tenant_id=1, store_id=1, body=body, operator="admin")
    grant_member_coupon(
        db,
        tenant_id=1,
        store_id=1,
        body=MemberCouponGrantIn(template_id=tpl.id, member_phone=str(new_member.phone)),
        operator="admin",
    )
    reminder = list_member_card_coupons_for_reminder(db, member_id=int(new_member.id), store_id=1)
    assert reminder.count == 1
    assert reminder.max_discount_yuan == "10.00"
    assert reminder.coupons[0].template_name == "提醒测试券"
