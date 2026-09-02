"""Hello轻厨袋贴：按单打印在餐别下展示份数，且不超出 75×50mm。"""

from app.schemas.store_print import DELIVERY_ENJOY_MEAL_KEY, LabelItemIn
from app.services.print.label_renderer import render_label_payload


def _item(**kwargs: object) -> LabelItemIn:
    data: dict[str, object] = {
        "name": "曹女士",
        "meal_category": "午餐+果蔬汁卡",
        "units": 3,
        "delivery_date": "2026-07-24",
        "order_kind": "delivery",
    }
    data.update(kwargs)
    return LabelItemIn.model_validate(data)


def _texts(copies_mode: str, **item_kw: object) -> list[str]:
    payload = render_label_payload(
        _item(**item_kw),
        DELIVERY_ENJOY_MEAL_KEY,
        paper_width_mm=76,
        paper_height_mm=130,
        copies_mode=copies_mode,
    )
    assert payload.lodop_layout is not None
    return [b.text for b in payload.lodop_layout.blocks]


def test_per_unit_does_not_show_units_line() -> None:
    texts = _texts("per_unit")
    assert any(t.startswith("餐别：") for t in texts)
    assert not any(t.startswith("份数：") for t in texts)


def test_per_order_shows_units_after_meal() -> None:
    texts = _texts("per_order", units=3)
    assert "份数：3份" in texts
    meal_i = next(i for i, t in enumerate(texts) if t.startswith("餐别："))
    assert texts[meal_i + 1] == "份数：3份"


def test_per_order_fits_single_75x50_sheet() -> None:
    payload = render_label_payload(
        _item(units=8),
        DELIVERY_ENJOY_MEAL_KEY,
        paper_width_mm=76,
        paper_height_mm=130,
        copies_mode="per_order",
    )
    layout = payload.lodop_layout
    assert layout is not None
    assert layout.paper_width_mm == 75
    assert layout.paper_height_mm == 50
    bottoms = [float(b.y_mm) + float(b.height_mm or 0) for b in layout.blocks]
    assert bottoms
    assert max(bottoms) <= 50 - 1.0
    assert any(b.text.startswith("日期：") for b in layout.blocks)
    assert payload.feie_xp_content and "份数：8份" in payload.feie_xp_content
    assert payload.yilian_content and "份数：8份" in payload.yilian_content
