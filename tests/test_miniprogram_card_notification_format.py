"""小程序自助购卡系统消息：多行正文与旧版升级。"""

from __future__ import annotations

from datetime import date

from app.services.admin_system_notification_service import (
    _is_legacy_miniprogram_card_order_pending_notification_message,
    _mask_phone_middle_four,
    _miniprogram_card_order_pending_message,
    _system_notification_message_phone_unmasked,
)


def test_mask_phone_middle_four() -> None:
    assert _mask_phone_middle_four("13800138000") == "138****8000"
    assert _mask_phone_middle_four(None) == "无手机号"
    assert _mask_phone_middle_four("") == "无手机号"


def test_phone_unmasked_detection() -> None:
    masked_body, _ = _miniprogram_card_order_pending_message(
        order_id=1,
        card_kind="周卡",
        member_id=1,
        member_phone="13800138000",
        member_name="a",
        delivery_start_date=None,
    )
    assert _system_notification_message_phone_unmasked(masked_body) is False
    assert _system_notification_message_phone_unmasked("手机号：13800138000") is True


def test_build_new_format_separates_uid_and_phone() -> None:
    title, body = _miniprogram_card_order_pending_message(
        order_id=969,
        card_kind="周卡",
        member_id=153115578978455,
        member_phone="13800138000",
        member_name="雪",
        delivery_start_date=date(2026, 6, 16),
    )
    assert title == "小程序自助购卡待核对 · 工单#969"
    assert "用户：雪" in body
    assert "会员UID：153115578978455" in body
    assert "手机号：138****8000" in body
    assert "13800138000" not in body
    assert "卡型：周卡" in body
    assert "支付方式：微信支付" in body
    assert "入账状态：餐次已入账" in body
    assert "起送日：2026-06-16" in body
    assert "mid=" not in body


def test_legacy_detection() -> None:
    legacy = (
        "会员 mid=153115578978455 13800138000 「雪」"
        "已微信支付购买周卡，餐次已入账；起送日 2026-06-16。"
        "请在「开卡工单」核对配送方式与起送日，完善后用户即可参与派单。"
    )
    assert _is_legacy_miniprogram_card_order_pending_notification_message(legacy) is True

    new_title, new_body = _miniprogram_card_order_pending_message(
        order_id=1,
        card_kind="月卡",
        member_id=1,
        member_phone="1",
        member_name="a",
        delivery_start_date=None,
    )
    assert new_title
    assert _is_legacy_miniprogram_card_order_pending_notification_message(new_body) is False
