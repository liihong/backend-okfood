"""菜品配餐饮指向饮品库，不指向零售果蔬汁。"""

import pytest
from pydantic import ValidationError

from app.schemas.admin import DishAdminOut, DishUpsertIn, WeeklySlotAssignIn
from app.schemas.menu_drink import DrinkUpsertIn


def test_dish_upsert_paired_drink_defaults_empty() -> None:
    body = DishUpsertIn(name="香菇蒸滑鸡")
    assert body.paired_drink_id is None


def test_dish_upsert_rejects_non_positive_drink_id() -> None:
    with pytest.raises(ValidationError):
        DishUpsertIn(name="香菇蒸滑鸡", paired_drink_id=0)


def test_drink_upsert_requires_name() -> None:
    body = DrinkUpsertIn(name="柠檬气泡")
    assert body.is_enabled is True
    assert body.id is None


def test_weekly_slot_omitted_drink_is_not_a_clear() -> None:
    """不传 paired_drink_id 表示这一餐的随餐饮不动；显式 null 才是清空。"""
    omitted = WeeklySlotAssignIn(week_start="2026-11-09", slot=1, dish_id=3, meal_period="lunch")
    assert "paired_drink_id" not in omitted.model_fields_set
    cleared = WeeklySlotAssignIn(
        week_start="2026-11-09",
        slot=1,
        dish_id=3,
        meal_period="dinner",
        paired_drink_id=None,
    )
    assert "paired_drink_id" in cleared.model_fields_set
    assert cleared.paired_drink_id is None


def test_dish_admin_out_keeps_drink_name() -> None:
    out = DishAdminOut(
        id=1,
        name="香菇蒸滑鸡",
        description=None,
        image_url=None,
        is_enabled=True,
        paired_drink_id=8,
        paired_drink_name="柠檬气泡",
        single_order_price_yuan=None,
        spice_level=None,
        internal_view_sop=None,
        created_at="2026-11-12T00:00:00",
        last_used_date=None,
    )
    assert out.paired_drink_name == "柠檬气泡"
