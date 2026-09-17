"""全餐「与午餐一起配送」：无工单导入会员的推断，不可把分购午+晚当成连带扣次。"""

from app.services.meal_period.combo_with_lunch import (
    infer_combo_with_lunch_without_full_meal_order,
)


def test_import_full_meal_follows_store_combo_flag() -> None:
    """台账导入午+晚总次数同为全餐卡份数、本店勾选一起配送 → 连带扣晚餐。"""
    assert infer_combo_with_lunch_without_full_meal_order(
        has_paid_applied_order=False,
        has_lunch_pool=True,
        has_dinner_pool=True,
        lunch_quota=48,
        dinner_quota=48,
        store_combo_meals_grants={6, 48},
        store_has_active_combo_with_lunch=True,
    )


def test_any_paid_order_not_inferred_as_import_combo() -> None:
    """已买午餐卡/晚餐卡：即使晚餐池有导入残留，也不按全餐连带。"""
    assert not infer_combo_with_lunch_without_full_meal_order(
        has_paid_applied_order=True,
        has_lunch_pool=True,
        has_dinner_pool=True,
        lunch_quota=48,
        dinner_quota=48,
        store_combo_meals_grants={48},
        store_has_active_combo_with_lunch=True,
    )


def test_lunch_only_import_not_combo() -> None:
    assert not infer_combo_with_lunch_without_full_meal_order(
        has_paid_applied_order=False,
        has_lunch_pool=True,
        has_dinner_pool=False,
        lunch_quota=48,
        dinner_quota=0,
        store_combo_meals_grants={48},
        store_has_active_combo_with_lunch=True,
    )


def test_split_24_plus_24_not_combo() -> None:
    """分购月午餐+月晚餐（各 24 次）不得当成 48 次全餐连带。"""
    assert not infer_combo_with_lunch_without_full_meal_order(
        has_paid_applied_order=False,
        has_lunch_pool=True,
        has_dinner_pool=True,
        lunch_quota=24,
        dinner_quota=24,
        store_combo_meals_grants={6, 48},
        store_has_active_combo_with_lunch=True,
    )


def test_store_without_combo_flag_not_combo() -> None:
    """本店全餐卡是分送：导入全餐会员也不连带，应出现在晚餐大表。"""
    assert not infer_combo_with_lunch_without_full_meal_order(
        has_paid_applied_order=False,
        has_lunch_pool=True,
        has_dinner_pool=True,
        lunch_quota=48,
        dinner_quota=48,
        store_combo_meals_grants=set(),
        store_has_active_combo_with_lunch=False,
    )
