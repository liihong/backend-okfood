"""商城零售分类配送费规则（单元测试）。"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.store_retail_category import StoreRetailCategory
from app.services.retail.retail_delivery_fee import (
    MODE_EXTRA_RULE,
    MODE_INCLUDED,
    build_category_delivery_hint,
    compute_retail_delivery_fee,
    strikethrough_delivery_fee_yuan,
)
from app.services.retail.retail_order_lines import ResolvedRetailLine


def _line(category_id: int, qty: int) -> ResolvedRetailLine:
    spu = SimpleNamespace(category_id=category_id, id=1, title="馄饨")
    prod = SimpleNamespace(id=1, spec_label="默认")
    return ResolvedRetailLine(
        product=prod,
        spu=spu,
        display_title="馄饨",
        quantity=qty,
        unit_price_yuan=Decimal("15.00"),
        line_amount_yuan=Decimal("15.00") * qty,
    )


def test_build_hint_qty_threshold():
    cat = StoreRetailCategory(
        id=1,
        store_id=1,
        name="馄饨",
        sort_order=0,
        is_active=True,
        delivery_pricing_mode=MODE_EXTRA_RULE,
        delivery_rule={
            "rule_type": "qty_threshold_fee",
            "qty_unit_label": "盒",
            "fee_yuan": "5.00",
            "max_qty_inclusive": 5,
        },
    )
    hint = build_category_delivery_hint(cat)
    assert hint is not None
    assert "5盒" in hint
    assert "6盒" in hint


def test_included_category_no_fee():
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    fee, bd = compute_retail_delivery_fee(db, lines=[_line(9, 3)], store_pickup=False, store_id=1)
    assert fee == Decimal("0.00")
    assert bd == []


def test_extra_rule_fee_within_threshold():
    cat = StoreRetailCategory(
        id=9,
        store_id=1,
        name="馄饨",
        sort_order=0,
        is_active=True,
        delivery_pricing_mode=MODE_EXTRA_RULE,
        delivery_rule={
            "rule_type": "qty_threshold_fee",
            "fee_yuan": "5.00",
            "max_qty_inclusive": 5,
            "qty_unit_label": "盒",
        },
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [cat]
    fee, bd = compute_retail_delivery_fee(db, lines=[_line(9, 3)], store_pickup=False, store_id=1)
    assert fee == Decimal("5.00")
    assert len(bd) == 1
    assert bd[0].total_qty == 3


def test_strikethrough_when_free_over_threshold():
    cat = StoreRetailCategory(
        id=9,
        store_id=1,
        name="馄饨",
        sort_order=0,
        is_active=True,
        delivery_pricing_mode=MODE_EXTRA_RULE,
        delivery_rule={
            "rule_type": "qty_threshold_fee",
            "fee_yuan": "5.00",
            "max_qty_inclusive": 5,
            "qty_unit_label": "盒",
        },
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [cat]
    fee, bd = compute_retail_delivery_fee(db, lines=[_line(9, 6)], store_pickup=False, store_id=1)
    assert fee == Decimal("0.00")
    assert strikethrough_delivery_fee_yuan(bd) == Decimal("5.00")
    assert bd[0].list_fee_yuan == Decimal("5.00")


def test_extra_rule_free_over_threshold():
    cat = StoreRetailCategory(
        id=9,
        store_id=1,
        name="馄饨",
        sort_order=0,
        is_active=True,
        delivery_pricing_mode=MODE_EXTRA_RULE,
        delivery_rule={
            "rule_type": "qty_threshold_fee",
            "fee_yuan": "5.00",
            "max_qty_inclusive": 5,
            "qty_unit_label": "盒",
        },
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [cat]
    fee, bd = compute_retail_delivery_fee(db, lines=[_line(9, 6)], store_pickup=False, store_id=1)
    assert fee == Decimal("0.00")
    assert len(bd) == 1


def test_pickup_no_delivery_fee():
    cat = StoreRetailCategory(
        id=9,
        store_id=1,
        name="馄饨",
        sort_order=0,
        is_active=True,
        delivery_pricing_mode=MODE_EXTRA_RULE,
        delivery_rule={"rule_type": "qty_threshold_fee", "fee_yuan": "5", "max_qty_inclusive": 5},
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [cat]
    fee, _ = compute_retail_delivery_fee(db, lines=[_line(9, 2)], store_pickup=True, store_id=1)
    assert fee == Decimal("0.00")


def test_default_mode_is_included():
    cat = StoreRetailCategory(
        id=1,
        store_id=1,
        name="果蔬汁",
        sort_order=0,
        is_active=True,
        delivery_pricing_mode=MODE_INCLUDED,
        delivery_rule=None,
    )
    assert build_category_delivery_hint(cat) is None