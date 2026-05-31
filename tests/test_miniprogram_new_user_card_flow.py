"""
小程序「新用户卡包购卡」支付回调链路自测（不依赖真实 MySQL / 微信）。

验证目标（与用户端流程一致）：
1. 创建工单：未缴、未入账、无起送日
2. 支付回调/拉单：已缴、次数即时入账、未完善配送时不激活、产生待核对配送系统消息
3. 完善配送：起送日可写入工单（含拉单滞后仍为未缴的补救），完善后激活参与派单
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.wechat_pay_v2 import WeChatPayV2Error, WechatPayNotifyParsed
from app.models.admin_system_notification import AdminSystemNotification
from app.models.enums import CardOrderPayStatus, CardPayChannel
from app.models.member import Member
from app.models.membership_card_template import MembershipCardTemplate
from app.services.admin_system_notification_service import KIND_MINIPROGRAM_CARD_ORDER_PENDING
from app.services.member_card_order_service import (
    apply_delivery_start_to_pending_miniprogram_card_order,
    member_paid_card_awaiting_setup,
)
from app.services.member_card_pay_service import (
    create_miniprogram_member_card_order,
    finalize_member_card_order_wechat_pay,
    get_member_card_order_for_user,
    prepare_wechat_jsapi_for_member_card_order,
    sync_member_card_order_from_wechat_query,
)
from app.core.timeutil import min_member_delivery_start_shanghai
from app.services.member_service import patch_member_profile


def _mock_pay_cfg() -> object:
    """测试用微信支付合并配置（避免依赖 tenant_integration_settings 表）。"""
    return type(
        "PayCfg",
        (),
        {
            "wx_mini_appid": "wx_test_appid",
            "wechat_pay_api_key": "01234567890123456789012345678901",
        },
    )()


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


def test_finalize_wechat_pay_new_user_credits_balance_with_notification(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    out_no = order.out_trade_no or ""
    bal_before = int(new_member.balance)
    grant = int(mall_template.meals_grant)

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
    assert row.applied_to_member is True
    assert row.wx_transaction_id == "4200001999TEST"
    assert mem is not None
    assert int(mem.balance) == bal_before + grant
    assert mem.is_active is False

    notif = db.scalars(
        select(AdminSystemNotification).where(
            AdminSystemNotification.kind == KIND_MINIPROGRAM_CARD_ORDER_PENDING,
            AdminSystemNotification.skip_reason == f"card_order_id:{int(row.id)}",
        )
    ).first()
    assert notif is not None
    assert "待核对" in (notif.title or "")
    assert "餐次已入账" in (notif.message or "")


def test_get_member_me_paid_card_not_awaiting_setup_after_credit(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    """支付后次数已入账：不应再标记 paid_card_awaiting_setup。"""
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    finalize_member_card_order_wechat_pay(
        db,
        WechatPayNotifyParsed(
            out_trade_no=order.out_trade_no or "",
            transaction_id="wx_await_setup",
            total_fee=18800,
        ),
    )
    assert member_paid_card_awaiting_setup(db, int(new_member.id)) is False
    db.expire_all()
    mem = db.get(Member, new_member.id)
    assert mem is not None
    assert int(mem.balance) == int(mall_template.meals_grant)


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
    assert row.applied_to_member is True


def test_apply_delivery_start_on_unpaid_wechat_order(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    """拉单滞后：用户先完善配送时，起送日仍应写入最近微信自助未缴工单。"""
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    assert order.pay_status == CardOrderPayStatus.UNPAID.value
    start = min_member_delivery_start_shanghai()
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
    start = min_member_delivery_start_shanghai()
    patched = apply_delivery_start_to_pending_miniprogram_card_order(
        db, int(new_member.id), start
    )
    assert patched is not None
    assert patched.delivery_start_date == start


def test_delivery_sheet_manual_attention_merges_same_day(
    db: Session,
) -> None:
    """同店同日恢复配送多次：系统消息合并，不触发唯一键冲突。"""
    from app.core.timeutil import today_shanghai
    from app.services.admin_system_notification_service import (
        KIND_DELIVERY_SHEET_MANUAL_ATTENTION,
        create_delivery_sheet_manual_attention_notification,
    )

    biz = today_shanghai()
    create_delivery_sheet_manual_attention_notification(
        db,
        store_id=1,
        business_date=biz,
        action_labels_cn=["取消暂停配送"],
        member_id=100,
        member_phone="13500001111",
        member_name="甲",
    )
    create_delivery_sheet_manual_attention_notification(
        db,
        store_id=1,
        business_date=biz,
        action_labels_cn=["取消暂停配送"],
        member_id=1187,
        member_phone="13261276633",
        member_name="乙",
    )
    db.commit()
    rows = list(
        db.scalars(
            select(AdminSystemNotification).where(
                AdminSystemNotification.store_id == 1,
                AdminSystemNotification.kind == KIND_DELIVERY_SHEET_MANUAL_ATTENTION,
                AdminSystemNotification.business_date == biz,
            )
        ).all()
    )
    assert len(rows) == 1
    assert "mid=100" in rows[0].message
    assert "mid=1187" in rows[0].message


def test_resume_delivery_patch_without_operation_log_table(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    """恢复配送：member_operation_logs 未建表时仍须成功（避免 PATCH /api/user/profile 500）。"""
    new_member.balance = int(mall_template.meals_grant)
    new_member.delivery_deferred = True
    new_member.is_active = False
    new_member.delivery_start_date = None
    db.commit()
    db.refresh(new_member)

    start = min_member_delivery_start_shanghai()
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
        patch(
            "app.services.admin_system_notification_service.store_should_prompt_manual_delivery_sheet_reconciliation",
            return_value=False,
        ),
    ):
        out = patch_member_profile(
            db,
            int(new_member.id),
            set_delivery_start=True,
            delivery_start_date=start,
            set_delivery_deferred=True,
            delivery_deferred=False,
            set_store_pickup=True,
            store_pickup=True,
            set_daily_meal_units=True,
            daily_meal_units=1,
        )
    assert out.delivery_deferred is False
    assert out.is_active is True
    assert out.delivery_start_date == start


def test_profile_patch_after_pay_activates_when_balance_ready(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
) -> None:
    """完善配送信息：支付后次数已入账，补齐起送日即激活参与派单。"""
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
    start = min_member_delivery_start_shanghai()
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
    assert out.is_active is True
    assert int(out.balance) == int(mall_template.meals_grant)

    db.expire_all()
    row = db.get(type(order), order.id)
    assert row is not None
    assert row.delivery_start_date == start
    assert row.applied_to_member is True


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
    assert int(mem.balance) == int(mall_template.meals_grant)


@patch(
    "app.services.member_card_pay_service.wechat_pay_misconfiguration_detail_merged",
    return_value=None,
)
@patch(
    "app.services.member_card_pay_service.get_merged_pay_config",
    return_value=_mock_pay_cfg(),
)
@patch("app.services.member_card_pay_service.close_order_by_out_trade_no")
@patch("app.services.member_card_pay_service.unified_order_jsapi")
@patch("app.services.member_card_pay_service.query_order_by_out_trade_no")
def test_prepare_wechat_jsapi_rotates_out_trade_no_when_wx_amount_differs(
    mock_query: object,
    mock_unified: object,
    mock_close: object,
    _mock_pay: object,
    _mock_perr: object,
    db: Session,
    new_member: Member,
    mall_template: MembershipCardTemplate,
) -> None:
    """继续支付：微信侧仍为首次下单金额时，须关单并轮换商户单号再统一下单。"""
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    old_out = order.out_trade_no or ""
    mock_query.return_value = {
        "result_code": "SUCCESS",
        "trade_state": "NOTPAY",
        "total_fee": "17800",
    }
    mock_unified.return_value = "prepay_rotated_ok"

    params = prepare_wechat_jsapi_for_member_card_order(
        db, int(new_member.id), int(order.id), "127.0.0.1"
    )

    assert params.get("paySign")
    mock_close.assert_called_once()
    db.refresh(order)
    assert (order.out_trade_no or "") != old_out
    assert (order.out_trade_no or "").startswith(f"OKC{int(order.id)}")
    mock_unified.assert_called_once()
    call_kw = mock_unified.call_args.kwargs
    assert call_kw["out_trade_no"] == order.out_trade_no
    assert call_kw["total_fee_fen"] == 18800


@patch(
    "app.services.member_card_pay_service.wechat_pay_misconfiguration_detail_merged",
    return_value=None,
)
@patch(
    "app.services.member_card_pay_service.get_merged_pay_config",
    return_value=_mock_pay_cfg(),
)
@patch("app.services.member_card_pay_service.close_order_by_out_trade_no")
@patch("app.services.member_card_pay_service.unified_order_jsapi")
@patch("app.services.member_card_pay_service.query_order_by_out_trade_no")
def test_prepare_wechat_jsapi_retries_on_wechat_reentry_mismatch(
    mock_query: object,
    mock_unified: object,
    mock_close: object,
    _mock_pay: object,
    _mock_perr: object,
    db: Session,
    new_member: Member,
    mall_template: MembershipCardTemplate,
) -> None:
    """统一下单返回「重入参数不一致」时，关单轮换商户单号并重试一次。"""
    order = create_miniprogram_member_card_order(
        db, int(new_member.id), membership_template_id=int(mall_template.id)
    )
    old_out = order.out_trade_no or ""
    mock_query.return_value = {"result_code": "FAIL", "err_code": "ORDERNOTEXIST"}
    mock_unified.side_effect = [
        WeChatPayV2Error(400, "请求重入时，参数与首次请求时不一致"),
        "prepay_after_retry",
    ]

    params = prepare_wechat_jsapi_for_member_card_order(
        db, int(new_member.id), int(order.id), "127.0.0.1"
    )

    assert params.get("package", "").startswith("prepay_id=")
    assert mock_unified.call_count == 2
    mock_close.assert_called_once()
    db.refresh(order)
    assert (order.out_trade_no or "") != old_out
