"""商城/零售备餐面单：SKU 分行渲染"""

from app.schemas.store_print import LabelItemIn
from app.services.print.label_renderer import (
    _build_meal_full_lines,
    _build_sf_waybill_table_html,
    _retail_mall_sku_lines,
)


def test_retail_mall_sku_lines_multiline() -> None:
    item = LabelItemIn(
        product_title="冷萃果蔬汁 500ml ×1\n鸡胸肉沙拉 ×2",
        units=3,
        order_kind="mall",
    )
    assert _retail_mall_sku_lines(item) == ["冷萃果蔬汁 500ml ×1", "鸡胸肉沙拉 ×2"]


def test_retail_mall_sf_table_no_meal_prefix() -> None:
    item = LabelItemIn(
        region="东区",
        name="李女士",
        phone_masked="132****6633",
        product_title="冷萃果蔬汁 500ml ×1\n鸡胸肉沙拉 ×2",
        units=3,
        remark="少辣",
        order_no="OKF12345",
        order_kind="mall",
    )
    html = _build_sf_waybill_table_html(item)
    assert html.count("订单号：") == 1
    assert "东区</td>" in html or ">东区<" in html
    assert html.count('colspan="2"') >= 2
    assert "餐品：" not in html
    assert "数量：" not in html
    assert "冷萃果蔬汁 500ml ×1" in html
    assert "鸡胸肉沙拉 ×2" in html
    assert "font-size:11px" in html


def test_retail_mall_cloud_lines_one_per_sku() -> None:
    item = LabelItemIn(
        store_name="OK饭",
        region="东区",
        name="李女士",
        product_title="冷萃果蔬汁 500ml ×1\n鸡胸肉沙拉 ×2",
        units=3,
        remark="少辣",
        order_no="OKF12345",
        order_kind="mall",
    )
    line_models = _build_meal_full_lines(item)
    texts = [ln.text for ln in line_models]
    assert any(ln.text.startswith("订单号：") and ln.right_text == "东区" for ln in line_models)
    assert not any(ln.text == "东区" and not ln.right_text for ln in line_models)
    assert "餐品：" not in "".join(texts)
    assert "冷萃果蔬汁 500ml ×1" in texts
    assert "鸡胸肉沙拉 ×2" in texts
    assert "数量：3份" not in texts