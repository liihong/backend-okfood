"""顺丰推单系统消息：失败明细格式化与解析。"""

from __future__ import annotations

from datetime import datetime

from app.schemas.admin import SfSameCityPreviewRow, SfSameCityPushItemResult
from app.services.admin.admin_system_notification_service import (
    SF_PUSH_FAILURE_DETAIL_MARKER,
    build_sf_push_failure_details,
    compose_sf_push_notification_message,
    split_sf_push_notification_message,
)


class _FakeAgg:
    def __init__(self) -> None:
        self.group_area = "中心医院区域"
        self.address_line = "河南省新乡市 LINLEE大胖店"
        self.sub_lines = [
            {"member_id": 698, "name": "TPQ", "phone": "15675175210", "units": 1, "is_delivered": False},
        ]


def test_compose_and_split_failure_details() -> None:
    summary = "今日共推送 137 单，成功 136 单，失败 1 单"
    details = ["· TPQ · 156****5210 · 原因：配送地址缺少有效坐标"]
    full = compose_sf_push_notification_message(summary, details)
    assert SF_PUSH_FAILURE_DETAIL_MARKER in full
    head, parsed = split_sf_push_notification_message(full)
    assert head == summary
    assert parsed == details


def test_build_sf_push_failure_details_from_preview_and_agg() -> None:
    stop_id = "abc123456789abcd"
    preview = SfSameCityPreviewRow(
        stop_id=stop_id,
        group_area="中心医院区域",
        address_line="LINLEE大胖店",
        pickup_phone="13800000000",
        map_location_text="LINLEE大胖店",
        door_detail="",
        recv_address="LINLEE大胖店",
        recv_building="",
        recv_lng=113.8,
        recv_lat=35.2,
        recv_name="TPQ",
        recv_phone="15675175210",
        product_category="餐品",
        weight_kg=0.5,
        push_immediately=True,
        expect_delivery_at=datetime(2026, 8, 8, 12, 0, 0),
        remark=None,
        is_direct=False,
        vehicle_type="小轿车",
        is_insured=False,
        goods_value_yuan=None,
        subscription_pending_units=1,
        single_meal_count=0,
        selected=True,
        already_pushed=False,
    )
    results = [
        SfSameCityPushItemResult(
            stop_id=stop_id,
            ok=False,
            message="配送地址缺少有效坐标，不可推顺丰",
            sf_order_id=None,
        )
    ]
    lines = build_sf_push_failure_details(
        None,  # db 未用到（preview+agg 已足够）
        results=results,
        preview_rows=[preview],
        ags={stop_id: _FakeAgg()},
    )
    assert len(lines) == 1
    assert "TPQ" in lines[0]
    assert "5210" in lines[0]
    assert "配送地址缺少有效坐标" in lines[0]
