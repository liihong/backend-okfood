"""开菜单纯计算：毛菜克数按份数相乘，净菜再乘出成率，汇总后再换算成斤。"""

from datetime import date
from decimal import Decimal

from app.services.admin.prep_menu_service import (
    OverrideInput,
    SlotInput,
    SopLineCalcIn,
    build_week_estimate,
)

WEEK = date(2026, 11, 2)


def _cauliflower(qty: str, rate: str = "0.70", ingredient_id: int = 1) -> SopLineCalcIn:
    return SopLineCalcIn(
        ingredient_id=ingredient_id,
        name="花菜",
        unit="g",
        gross_qty_per_portion=Decimal(qty),
        yield_rate=Decimal(rate),
    )


def _day(estimate, meal: str, slot: int):
    meal_row = next(item for item in estimate.meals if item.meal_period == meal)
    return next(item for item in meal_row.days if item.slot == slot)


def test_weight_uses_gross_grams_then_yield() -> None:
    """花菜单份毛菜 80 克、出成率 70%、100 份 → 毛菜 16.00 斤，净菜 11.20 斤。"""
    estimate = build_week_estimate(
        WEEK,
        [
            SlotInput(
                meal_period="lunch",
                slot=1,
                dish_id=9,
                dish_name="麻辣香锅",
                total_stock=100,
            )
        ],
        {9: [_cauliflower("80")]},
        [],
    )
    day = _day(estimate, "lunch", 1)
    assert day.status == "ok"
    assert day.portions_source == "total_stock"
    assert day.lines[0].gross_jin == "16.00"
    assert day.lines[0].net_jin == "11.20"
    assert day.lines[0].yield_rate == "0.7000"
    assert estimate.week_ingredient_summary[0].gross_jin == "16.00"
    assert estimate.week_ingredient_summary[0].net_jin == "11.20"


def test_piece_count_is_not_converted_to_jin() -> None:
    """鸡翅根 3 个 × 100 份 = 300 个，不出斤，也不乘出成率。"""
    wing = SopLineCalcIn(
        ingredient_id=2,
        name="鸡翅根",
        unit="piece",
        gross_qty_per_portion=Decimal("3"),
        yield_rate=Decimal("0.50"),
    )
    estimate = build_week_estimate(
        WEEK,
        [SlotInput("lunch", 1, 9, "麻辣香锅", 100)],
        {9: [wing]},
        [],
    )
    line = _day(estimate, "lunch", 1).lines[0]
    assert line.gross_count == "300"
    assert line.gross_jin is None
    assert line.net_jin is None
    assert line.yield_rate is None
    summary = estimate.week_ingredient_summary[0]
    assert summary.unit == "piece"
    assert summary.gross_count == "300"
    assert summary.gross_jin is None


def test_same_ingredient_is_summed_in_grams_before_jin() -> None:
    """两行各 3 克，逐行会进到 0.01 斤，合计 6 克仍是 0.01 斤。"""
    line = _cauliflower("3", rate="1")
    estimate = build_week_estimate(
        WEEK,
        [
            SlotInput("lunch", 1, 1, "甲", 1),
            SlotInput("dinner", 1, 2, "乙", 1),
        ],
        {1: [line], 2: [line]},
        [],
    )
    assert _day(estimate, "lunch", 1).lines[0].gross_jin == "0.01"
    assert _day(estimate, "dinner", 1).lines[0].gross_jin == "0.01"
    assert estimate.week_ingredient_summary[0].gross_jin == "0.01"
    assert estimate.week_ingredient_summary[0].net_jin == "0.01"


def test_two_dishes_add_before_rounding_across_meals() -> None:
    """午餐 80 克 × 10 份，晚餐同样，合计 3.20 斤，而不是两个 1.60 再有误差。"""
    line = _cauliflower("80", rate="1")
    estimate = build_week_estimate(
        WEEK,
        [
            SlotInput("lunch", 1, 1, "甲", 10),
            SlotInput("dinner", 3, 2, "乙", 10),
        ],
        {1: [line], 2: [line]},
        [],
    )
    lunch = next(item for item in estimate.meals if item.meal_period == "lunch")
    assert lunch.ingredient_summary[0].gross_jin == "1.60"
    assert estimate.week_ingredient_summary[0].gross_jin == "3.20"
    assert estimate.week_ingredient_summary[0].net_jin == "3.20"


def test_missing_portions_are_not_invented() -> None:
    """日总份为空且没有预估份数时，不估算，也不进入采购汇总。"""
    estimate = build_week_estimate(
        WEEK,
        [SlotInput("lunch", 2, 9, "麻辣香锅", None)],
        {9: [_cauliflower("80")]},
        [],
    )
    day = _day(estimate, "lunch", 2)
    assert day.status == "no_portions"
    assert day.has_sop is True
    assert day.lines == []
    assert estimate.week_ingredient_summary == []


def test_override_replaces_total_stock_without_changing_other_days() -> None:
    """临时份数只影响被覆盖的那一天；显式清空则不再回读日总份。"""
    slots = [
        SlotInput("lunch", 1, 9, "麻辣香锅", 100),
        SlotInput("lunch", 2, 9, "麻辣香锅", 100),
    ]
    sop = {9: [_cauliflower("80", rate="1")]}
    estimate = build_week_estimate(
        WEEK,
        slots,
        sop,
        [OverrideInput("lunch", 1, 50), OverrideInput("lunch", 2, None)],
    )
    monday = _day(estimate, "lunch", 1)
    tuesday = _day(estimate, "lunch", 2)
    assert monday.portions == 50
    assert monday.portions_source == "override"
    assert monday.lines[0].gross_jin == "8.00"
    assert tuesday.status == "no_portions"
    assert tuesday.portions is None
    assert estimate.week_ingredient_summary[0].gross_jin == "8.00"


def test_dish_without_sop_is_flagged_and_excluded() -> None:
    estimate = build_week_estimate(
        WEEK,
        [SlotInput("dinner", 4, 3, "鲜虾三鲜汤", 20)],
        {},
        [],
    )
    day = _day(estimate, "dinner", 4)
    assert day.status == "no_sop"
    assert day.portions == 20
    assert day.has_sop is False
    assert estimate.week_ingredient_summary == []


def test_empty_slot_stays_unscheduled() -> None:
    estimate = build_week_estimate(date(2026, 11, 5), [], {}, [])
    assert estimate.week_start == "2026-11-02"
    day = _day(estimate, "lunch", 1)
    assert day.status == "no_dish"
    assert day.menu_date == "2026-11-02"
    assert len(estimate.meals) == 2
    assert len(estimate.meals[0].days) == 7
