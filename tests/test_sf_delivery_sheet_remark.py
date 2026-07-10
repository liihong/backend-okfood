"""顺丰大表推单备注：仅保留份数、用户/地址备注与商家说明。"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.delivery.sf_same_city_service import (
    _Agg,
    _build_sf_delivery_sheet_remark,
    _resolve_delivery_sheet_push_remark,
    _sf_product_display_name,
    _strip_sf_remark_noise,
    _strip_single_meal_labels_from_remark,
)
from app.schemas.admin import SfSameCityPreviewRow


def test_strip_sf_remark_noise_removes_legacy_fields():
    raw = "少辣 车型:小轿车 类别:外部落地配 期望送达12:00"
    assert _strip_sf_remark_noise(raw) == "少辣"


def test_strip_single_meal_labels_from_remark():
    raw = "少辣；宫保鸡丁x1；放门口"
    assert _strip_single_meal_labels_from_remark(raw) == "少辣；放门口"


def test_build_sf_delivery_sheet_remark_meal_count_and_user_notes():
    assert _build_sf_delivery_sheet_remark(meal_count=2, remark="少辣；不要香菜") == "2份餐 少辣；不要香菜"
    assert _build_sf_delivery_sheet_remark(meal_count=1, remark=None) == "1份餐"


def test_resolve_delivery_sheet_push_remark_prefers_subscription_notes():
    agg = _Agg(
        stop_id="s1",
        group_area="A区",
        address_line="某路1号",
        sub_lines=[
            {"member_id": 1, "units": 2, "is_delivered": False, "remarks": "少辣"},
        ],
    )
    assert _resolve_delivery_sheet_push_remark("少辣；宫保鸡丁x1", agg) == "少辣"


def test_resolve_delivery_sheet_push_remark_keeps_merchant_override():
    agg = _Agg(
        stop_id="s1",
        group_area="A区",
        address_line="某路1号",
        sub_lines=[
            {"member_id": 1, "units": 2, "is_delivered": False, "remarks": "少辣"},
        ],
    )
    assert _resolve_delivery_sheet_push_remark("请先电话联系", agg) == "请先电话联系"


def test_sf_product_display_name_hides_external_category():
    gset = SimpleNamespace(SF_PRODUCT_CATEGORY_LABEL="外部落地配")
    row = SfSameCityPreviewRow(
        stop_id="stop-12345678",
        pickup_phone="13800000000",
        weight_kg=1.0,
        product_category="外部落地配",
    )
    assert _sf_product_display_name(row, n_meals=2, gset=gset) == "餐品2份"

    row2 = row.model_copy(update={"product_category": "招牌牛肉饭"})
    assert _sf_product_display_name(row2, n_meals=1, gset=gset) == "招牌牛肉饭 1份"
