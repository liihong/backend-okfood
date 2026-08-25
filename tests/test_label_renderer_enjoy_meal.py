"""标签渲染：Hello轻厨用餐愉快袋贴（75×50 单张）。"""

from __future__ import annotations

from app.schemas.store_print import (
    DELIVERY_ENJOY_MEAL_KEY,
    ENJOY_MEAL_PAPER_HEIGHT_MM,
    ENJOY_MEAL_PAPER_WIDTH_MM,
    LabelItemIn,
)
from app.services.admin.store_print_service import list_print_templates
from app.services.print.label_renderer import render_label_payload


def _enjoy_item() -> LabelItemIn:
    return LabelItemIn(
        name="曹女士",
        meal_category="午餐+果蔬汁卡",
        delivery_date="2026-07-24",
        store_name="Hello轻厨",
        order_kind="delivery",
    )


def test_enjoy_meal_fits_one_75x50_label() -> None:
    payload = render_label_payload(
        _enjoy_item(),
        DELIVERY_ENJOY_MEAL_KEY,
        paper_width_mm=76,
        paper_height_mm=130,
    )
    layout = payload.lodop_layout
    assert layout is not None
    assert layout.layout_style == "enjoy_meal"
    assert layout.paper_width_mm == ENJOY_MEAL_PAPER_WIDTH_MM
    assert layout.paper_height_mm == ENJOY_MEAL_PAPER_HEIGHT_MM
    assert layout.content_height_mm == float(ENJOY_MEAL_PAPER_HEIGHT_MM)
    assert not layout.barcodes
    texts = [b.text for b in layout.blocks]
    joined = "\n".join(texts)
    assert "用餐愉快哦" in joined
    assert "姓名：曹女士" in joined
    assert "餐别：午+果" in joined
    assert "酱汁根据个人口味酌量添加" in joined
    assert "优先建议冷藏保鲜" in joined
    assert "日期：2026/07/24" in joined
    assert "扫码添加好友" not in joined
    bottoms = [float(b.y_mm) + float(b.height_mm or 0) for b in layout.blocks]
    assert max(bottoms) <= ENJOY_MEAL_PAPER_HEIGHT_MM
    assert min(float(b.x_mm) for b in layout.blocks) <= 2.0
    assert min(float(b.y_mm) for b in layout.blocks) <= 2.0


def test_enjoy_meal_feie_size_is_75x50_without_qr() -> None:
    payload = render_label_payload(
        _enjoy_item(),
        DELIVERY_ENJOY_MEAL_KEY,
        paper_width_mm=76,
        paper_height_mm=130,
    )
    xml = payload.feie_xp_content or ""
    assert "曹女士" in xml
    assert "午+果" in xml
    assert "<QR" not in xml
    assert "扫码添加好友" not in xml
    assert "<SIZE>" in xml


def test_enjoy_meal_template_only_listed_for_tenant_3() -> None:
    keys_t3 = {t["key"] for t in list_print_templates("delivery_sheet", tenant_id=3)}
    keys_t1 = {t["key"] for t in list_print_templates("delivery_sheet", tenant_id=1)}
    assert DELIVERY_ENJOY_MEAL_KEY in keys_t3
    assert DELIVERY_ENJOY_MEAL_KEY not in keys_t1
