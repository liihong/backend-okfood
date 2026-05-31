"""
小程序「新用户卡包购卡」支付回调链路自测（不依赖真实 MySQL / 微信）。

验证目标（与用户端流程一致，不含后台人工确认入账）：
1. 创建工单：未缴、未入账、无起送日
2. 支付回调/拉单：已缴、仍未入账、会员次数不变、产生待审批系统消息
3. 完善配送：起送日可写入工单（含拉单滞后仍为未缴的补救）
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.wechat_pay_v2 import WechatPayNotifyParsed
from app.models.admin_system_notification import AdminSystemNotification
from app.models.enums import CardOrderPayStatus, CardPayChannel
from app.models.member import Member
from app.models.membership_card_template import MembershipCardTemplate
from app.services.admin_system_notification_service import KIND_MINIPROGRAM_CARD_ORDER_PENDING
from app.services.member_card_order_service import (
    apply_delivery_start_to_pending_miniprogram_card_order,
)
from app.services.member_card_pay_service import (
    create_miniprogram_member_card_order,
    finalize_member_card_order_wechat_pay,
    get_member_card_order_for_user,
    sync_member_card_order_from_wechat_query,
)
from app.services.member_service import patch_member_profile


def test_new_user_create_order_unpaid_no_delivery_date(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    order = create_miniprogram_member_card_order(
        db,
        int(new_member.id),
        membership_template_id=int(mall_template.id),
    )
    assert order.pay_status == CardOrderPayStatus.UNPAID.value
    assert order.applied_to_member is False
    assert order.delivery_start_date is None
    assert order.created_by == "miniprogram"
    assert order.pay_channel == CardPayChannel.WECHAT.value
    assert order.amount_yuan == Decimal("188.00")
    assert (order.out_trade_no or "").startswith("OKC")


def test_get_member_card_order_for_user(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    order = create_miniprogram_member_card_order(
        db,
        int(new_member.id),
        membership_template_id=int(mall_template.id),
    )
    payload = get_member_card_order_for_user(db, int(new_member.id), int(order.id))
    assert int(payload["id"]) == int(order.id)
    assert payload["pay_status"] == CardOrderPayStatus.UNPAID.value


def test_finalize_wechat_pay_new_user_paid_not_synced_with_notification(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    out_no = order.out_trade_no or ""
    bal_before = int(new_member.balance)

    ok, reason = finalize_member_card_order_wechat_pay(
        db,
        WechatPayNotifyParsed(
            out_trade_no=out_no,
            transaction_id="4200001999TEST",
            total_fee=18800,
        ),
    )
    assert ok is True
    assert reason in ("paid", "already_paid")

    db.expire_all()
    row = db.get(type(order), order.id)
    mem = db.get(Member, new_member.id)
    assert row is not None
    assert row.pay_status == CardOrderPayStatus.PAID.value
    assert row.applied_to_member is False
    assert row.wx_transaction_id == "4200001999TEST"
    assert mem is not None
    assert int(mem.balance) == bal_before

    notif = db.scalars(
        select(AdminSystemNotification).where(
            AdminSystemNotification.kind == KIND_MINIPROGRAM_CARD_ORDER_PENDING,
            AdminSystemNotification.skip_reason == f"card_order_id:{int(row.id)}",
        )
    ).first()
    assert notif is not None
    assert "待审批" in (notif.title or "")
    assert "确认入账" in (notif.message or "")


def test_sync_query_same_as_notify_finalize(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    """小程序支付后拉单与异步通知走同一 finalize。"""
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    out_no = order.out_trade_no or ""

    mock_resp = {
        "result_code": "SUCCESS",
        "trade_state": "SUCCESS",
        "out_trade_no": out_no,
        "transaction_id": "wx_sync_test",
        "total_fee": "18800",
    }
    with patch(
        "app.services.member_card_pay_service.query_order_by_out_trade_no",
        return_value=mock_resp,
    ):
        with patch(
            "app.services.member_card_pay_service.get_merged_pay_config",
            return_value=object(),
        ):
            ok, reason = sync_member_card_order_from_wechat_query(
                db, int(new_member.id), int(order.id)
            )
    assert ok is True
    db.expire_all()
    row = db.get(type(order), order.id)
    assert row is not None
    assert row.pay_status == CardOrderPayStatus.PAID.value
    assert row.applied_to_member is False


def test_apply_delivery_start_on_unpaid_wechat_order(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    """拉单滞后：用户先完善配送时，起送日仍应写入最近微信自助未缴工单。"""
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    assert order.pay_status == CardOrderPayStatus.UNPAID.value
    start = date.today()
    patched = apply_delivery_start_to_pending_miniprogram_card_order(
        db, int(new_member.id), start
    )
    assert patched is not None
    assert int(patched.id) == int(order.id)
    assert patched.delivery_start_date == start


def test_apply_delivery_start_on_paid_unapplied_order(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    finalize_member_card_order_wechat_pay(
        db,
        WechatPayNotifyParsed(
            out_trade_no=order.out_trade_no or "",
            transaction_id="wx1",
            total_fee=18800,
        ),
    )
    start = date.today()
    patched = apply_delivery_start_to_pending_miniprogram_card_order(
        db, int(new_member.id), start
    )
    assert patched is not None
    assert patched.delivery_start_date == start


def test_profile_patch_after_pay_does_not_activate_without_balance(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    """完善配送信息：有起送日但 balance=0 时不激活（不进配送大表）。"""
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    finalize_member_card_order_wechat_pay(
        db,
        WechatPayNotifyParsed(
            out_trade_no=order.out_trade_no or "",
            transaction_id="wx2",
            total_fee=18800,
        ),
    )
    start = date.today()
    with (
        patch(
            "app.services.member_service.guard_member_self_service_during_sf_fulfillment",
            return_value=None,
        ),
        patch(
            "app.services.sf_order_fulfillment_service.member_sf_self_service_locked_on_delivery_date",
            return_value=False,
        ),
        patch("app.services.member_service.get_default_address", return_value=None),
        patch("app.services.member_service.record_member_operation"),
    ):
        out = patch_member_profile(
            db,
            int(new_member.id),
            set_delivery_start=True,
            delivery_start_date=start,
            set_delivery_deferred=True,
            delivery_deferred=False,
            set_store_pickup=True,
            store_pickup=False,
        )
    assert out.delivery_start_date == start
    assert out.is_active is False
    assert int(out.balance) == 0

    db.expire_all()
    row = db.get(type(order), order.id)
    assert row is not None
    assert row.delivery_start_date == start
    assert row.applied_to_member is False


def test_two_card_orders_same_day_both_create_pending_notifications(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    """同日多笔小程序购卡：待审批通知须各工单一条，不得触发唯一键冲突导致支付同步 500。"""
    m2 = Member(
        tenant_id=1,
        store_id=1,
        phone="13500002222",
        name="用户二",
        balance=0,
        meal_quota_total=0,
        wx_mini_openid="openid_second_user",
        is_active=False,
    )
    db.add(m2)
    db.commit()
    db.refresh(m2)

    o1 = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    o2 = create_miniprogram_member_card_order(
        db, int(m2.id), membership_template_id=int(mall_template.id)
    )
    for order in (o1, o2):
        ok, _ = finalize_member_card_order_wechat_pay(
            db,
            WechatPayNotifyParsed(
                out_trade_no=order.out_trade_no or "",
                transaction_id=f"wx_{order.id}",
                total_fee=18800,
            ),
        )
        assert ok is True

    notifs = list(
        db.scalars(
            select(AdminSystemNotification).where(
                AdminSystemNotification.kind == KIND_MINIPROGRAM_CARD_ORDER_PENDING,
            )
        ).all()
    )
    assert len(notifs) == 2
    markers = {n.skip_reason for n in notifs}
    assert f"card_order_id:{int(o1.id)}" in markers
    assert f"card_order_id:{int(o2.id)}" in markers


def test_finalize_idempotent_second_notify(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    parsed = WechatPayNotifyParsed(
        out_trade_no=order.out_trade_no or "",
        transaction_id="wx3",
        total_fee=18800,
    )
    assert finalize_member_card_order_wechat_pay(db, parsed)[0] is True
    ok2, reason2 = finalize_member_card_order_wechat_pay(db, parsed)
    assert ok2 is True
    assert reason2 == "already_paid"
    mem = db.get(Member, new_member.id)
    assert mem is not None
    assert int(mem.balance) == 0
