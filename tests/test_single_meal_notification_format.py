"""单次零售系统消息：多行正文与旧版升级。"""

from __future__ import annotations

from datetime import date, datetime

from app.services.admin.admin_system_notification_service import (
    _build_single_meal_order_paid_notification_text,
    _is_legacy_single_meal_paid_notification_message,
    supply_day_from_single_meal_notification_message,
)


def test_build_new_format_includes_member_card_note() -> None:
    title, body = _build_single_meal_order_paid_notification_text(
        order_id=199,
        delivery_date=date(2026, 6, 5),
        dish_name="泰式酸辣虾拌蕨根粉",
        quantity=1,
        store_pickup=False,
        member_phone="18637369306",
        member_name="隔壁老陈",
        order_created_at=datetime(2026, 6, 4, 17, 8, 35),
        out_trade_no="wx199",
        pay_channel="会员卡",
    )
    assert title == "单次零售新订单 · #199"
    assert "用户：隔壁老陈" in body
    assert "手机号：186****9306" in body
    assert "18637369306" not in body
    assert "餐品：泰式酸辣虾拌蕨根粉×1（会员卡支付）" in body
    assert "供餐日：2026-06-05（配送到家）" in body
    assert "trace=" not in body
    assert "mid=" not in body


def test_legacy_detection_and_supply_day_parse() -> None:
    legacy = (
        "会员 mid=32818637369306 「隔壁老陈」已支付 ¥0.00 泰式酸辣虾拌蕨根粉×1，"
        "供餐日 2026-06-05（配送到家）。请尽快在「订单管理」推送配送或安排自提。 trace=1780565971812-01255f38"
    )
    assert _is_legacy_single_meal_paid_notification_message(legacy) is True
    assert supply_day_from_single_meal_notification_message(legacy) == "2026-06-05"

    new_body, _ = _build_single_meal_order_paid_notification_text(
        order_id=1,
        delivery_date=date(2026, 6, 5),
        dish_name="菜",
        quantity=1,
        store_pickup=False,
        member_phone="1",
        member_name="a",
        order_created_at=None,
        out_trade_no=None,
        pay_channel=None,
    )
    assert _is_legacy_single_meal_paid_notification_message(new_body) is False
