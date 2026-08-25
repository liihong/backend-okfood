"""标签渲染：Hello轻厨用餐愉快袋贴。"""

from __future__ import annotations

from app.schemas.store_print import DELIVERY_ENJOY_MEAL_KEY, LabelItemIn
from app.services.admin.store_print_service import list_print_templates
from app.services.print.label_renderer import render_label_payload


def _enjoy_item() -> LabelItemIn:
    return LabelItemIn(
        name="曹女士",
        meal_category="午餐+果蔬汁卡",
        delivery_date="2026-07-24",
        store_name="Hello轻厨",
        qr_content="https://example.com/hello-friend",
        order_kind="delivery",
    )


def test_enjoy_meal_lodop_layout_matches_bag_sticker() -> None:
    payload = render_label_payload(
        _enjoy_item(),
        DELIVERY_ENJOY_MEAL_KEY,
        paper_width_mm=60,
        paper_height_mm=90,
    )
    layout = payload.lodop_layout
    assert layout is not None
    assert layout.layout_style == "enjoy_meal"
    html = layout.table_html
    assert "用餐愉快哦" in html
    assert "姓名：曹女士" in html
    assert "餐别：午+果" in html
    assert "酱汁根据个人口味酌量添加" in html
    assert "优先建议冷藏保鲜" in html
    assert "日期：2026/07/24" in html
    assert "扫码添加好友" in html
    assert layout.barcodes
    assert layout.barcodes[0].code == "https://example.com/hello-friend"
    assert layout.barcodes[0].code_type == "QRCode"


def test_enjoy_meal_feie_xml_contains_qr() -> None:
    payload = render_label_payload(
        _enjoy_item(),
        DELIVERY_ENJOY_MEAL_KEY,
        paper_width_mm=60,
        paper_height_mm=90,
    )
    xml = payload.feie_xp_content or ""
    assert "曹女士" in xml
    assert "午+果" in xml
    assert "<QR" in xml
    assert "https://example.com/hello-friend" in xml


def test_enjoy_meal_template_only_listed_for_tenant_3() -> None:
    keys_t3 = {t["key"] for t in list_print_templates("delivery_sheet", tenant_id=3)}
    keys_t1 = {t["key"] for t in list_print_templates("delivery_sheet", tenant_id=1)}
    assert DELIVERY_ENJOY_MEAL_KEY in keys_t3
    assert DELIVERY_ENJOY_MEAL_KEY not in keys_t1
