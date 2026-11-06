"""包装扣库：后厨出餐含未售出，午餐和晚餐分开扣，重复跑不双扣。"""

from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.packaging_schema import ensure_packaging_schema
from app.jobs.packaging_consume import dates_to_consume
from app.models.packaging_sku import PackagingSku
from app.models.packaging_stock import PackagingStock
from app.models.packaging_stock_txn import PackagingStockTxn
from app.services.packaging import consume_service
from app.services.packaging.alert_service import build_alert_message
from app.services.packaging.constants import BAG_FLAG, PORTION_SOURCE_DELIVERED, PORTION_SOURCE_KITCHEN
from app.services.packaging.deduction import RecipeQty, plan_meal_deduction
from app.services.packaging.portions import MealPortions, resolve_portion_basis
from app.services.packaging.recipe_service import RecipeLineIn, _validate_lines
from app.services.packaging.stock_command_service import purchase_in, stocktake

DAY = date(2026, 11, 4)
STORE_ID = 1


def test_catchup_starts_the_day_after_opening_stock() -> None:
    """11 月 4 日下午录入的结存不再回扣当天，5 日到今天要补。"""
    today = date(2026, 11, 6)
    assert dates_to_consume(today, date(2026, 11, 4)) == [
        date(2026, 11, 5),
        date(2026, 11, 6),
    ]


def test_catchup_stops_at_seven_days() -> None:
    today = date(2026, 11, 20)
    dates = dates_to_consume(today, date(2026, 11, 1))
    assert dates[0] == today - timedelta(days=7)
    assert dates[-1] == today
    assert len(dates) == 8


def test_opening_day_still_runs_that_night() -> None:
    today = date(2026, 11, 4)
    assert dates_to_consume(today, today) == [today]


def test_no_stock_yet_still_checks_yesterday_and_today() -> None:
    today = date(2026, 11, 6)
    assert dates_to_consume(today, None) == [date(2026, 11, 5), today]


def test_kitchen_output_keeps_unsold_packages() -> None:
    """后厨出餐 10、实发 7 时按 10 扣，包好没卖出的也算损耗。"""
    portions, source = resolve_portion_basis(10, 7)
    assert portions == 10
    assert source == PORTION_SOURCE_KITCHEN
    plan = plan_meal_deduction(
        meal_label="午餐",
        portions=portions,
        portion_source=source,
        bag_sku_id=1,
        bag_ready=True,
        bag_name="打包袋",
        box_lines=[RecipeQty(2, 1, True, "900圆")],
        standard_lines=[RecipeQty(3, 1, True, "筷子")],
    )
    assert plan.quantities == {1: 10, 2: 10, 3: 10}
    assert plan.warnings == []


def test_lunch_and_dinner_use_their_own_boxes() -> None:
    """午餐 10 份 900圆、晚餐 8 份 650方，打包袋合计 18，两餐盒子不相加混用。"""
    lunch = plan_meal_deduction(
        meal_label="午餐",
        portions=10,
        portion_source=PORTION_SOURCE_KITCHEN,
        bag_sku_id=1,
        bag_ready=True,
        bag_name="打包袋",
        box_lines=[RecipeQty(2, 1, True, "900圆")],
        standard_lines=[],
    )
    dinner = plan_meal_deduction(
        meal_label="晚餐",
        portions=8,
        portion_source=PORTION_SOURCE_KITCHEN,
        bag_sku_id=1,
        bag_ready=True,
        bag_name="打包袋",
        box_lines=[RecipeQty(4, 1, True, "650方")],
        standard_lines=[],
    )
    assert lunch.quantities[2] == 10
    assert 4 not in lunch.quantities
    assert dinner.quantities[4] == 8
    assert 2 not in dinner.quantities
    assert lunch.quantities[1] + dinner.quantities[1] == 18


def test_bag_in_box_line_is_not_deducted_twice() -> None:
    plan = plan_meal_deduction(
        meal_label="午餐",
        portions=10,
        portion_source=PORTION_SOURCE_KITCHEN,
        bag_sku_id=1,
        bag_ready=True,
        bag_name="打包袋",
        box_lines=[RecipeQty(1, 1, True, "打包袋")],
        standard_lines=[RecipeQty(1, 1, True, "打包袋")],
    )
    assert plan.quantities[1] == 10


def test_missing_kitchen_output_falls_back_and_warns() -> None:
    portions, source = resolve_portion_basis(None, 6)
    assert portions == 6
    assert source == PORTION_SOURCE_DELIVERED
    plan = plan_meal_deduction(
        meal_label="晚餐",
        portions=portions,
        portion_source=source,
        bag_sku_id=1,
        bag_ready=True,
        bag_name="打包袋",
        box_lines=[RecipeQty(2, 1, True, "650方")],
        standard_lines=[],
    )
    assert plan.quantities[1] == 6
    assert any("未填后厨出餐" in item for item in plan.warnings)


def test_unready_bag_is_not_deducted() -> None:
    plan = plan_meal_deduction(
        meal_label="午餐",
        portions=10,
        portion_source=PORTION_SOURCE_KITCHEN,
        bag_sku_id=1,
        bag_ready=False,
        bag_name="打包袋",
        box_lines=[],
        standard_lines=[],
    )
    assert 1 not in plan.quantities
    assert any("尚未期初" in item for item in plan.warnings)
    assert any("未设置用盒" in item for item in plan.warnings)


def test_alert_message_stays_within_column() -> None:
    lows = [
        {
            "name": f"耗材{index:02d}",
            "qty": 1,
            "unit": "个",
            "safety_stock": 9,
            "supplier_name": "供应商名称很长" * 3,
            "is_meal_bag": False,
        }
        for index in range(80)
    ]
    message = build_alert_message(["午餐未设置用盒，餐盒未扣"], lows)
    assert len(message) <= 2000
    assert "另有" in message


def test_recipe_rejects_meal_bag(db) -> None:
    bag = PackagingSku(store_id=STORE_ID, name="打包袋", unit="个", bag_flag=BAG_FLAG, is_active=True)
    db.add(bag)
    db.flush()
    with pytest.raises(HTTPException) as caught:
        _validate_lines(db, [RecipeLineIn(sku_id=int(bag.id), qty_per_portion=1)], store_id=STORE_ID)
    assert caught.value.status_code == 400


def test_consume_lunch_and_dinner_once(db, monkeypatch) -> None:
    bag = _sku(db, "打包袋", bag=True)
    lunch_box = _sku(db, "900圆")
    dinner_box = _sku(db, "650方")
    chopsticks = _sku(db, "筷子")
    for sku in (bag, lunch_box, dinner_box, chopsticks):
        purchase_in(db, store_id=STORE_ID, sku_id=int(sku.id), qty=100, operator="tester", remark=None, biz_date=DAY)

    def fake_portions(_db, *, store_id, biz_date, meal_period):
        _ = (store_id, biz_date)
        portions = 10 if meal_period == "lunch" else 8
        return MealPortions(portions=portions, source=PORTION_SOURCE_KITCHEN, kitchen_output=portions)

    def fake_boxes(_db, *, store_id, biz_date, meal_period):
        _ = (store_id, biz_date)
        if meal_period == "lunch":
            return [RecipeQty(int(lunch_box.id), 1, True, "900圆")]
        return [RecipeQty(int(dinner_box.id), 1, True, "650方")]

    monkeypatch.setattr(consume_service, "meal_portions", fake_portions)
    monkeypatch.setattr(consume_service, "_slot_recipe", fake_boxes)
    monkeypatch.setattr(
        consume_service,
        "_standard_recipe",
        lambda *_args, **_kwargs: [RecipeQty(int(chopsticks.id), 1, True, "筷子")],
    )

    assert consume_service.consume_meal(db, store_id=STORE_ID, biz_date=DAY, meal_period="lunch") is True
    assert consume_service.consume_meal(db, store_id=STORE_ID, biz_date=DAY, meal_period="dinner") is True
    assert consume_service.consume_meal(db, store_id=STORE_ID, biz_date=DAY, meal_period="lunch") is False

    assert _qty(db, bag.id) == 100 - 18
    assert _qty(db, lunch_box.id) == 90
    assert _qty(db, dinner_box.id) == 92
    assert _qty(db, chopsticks.id) == 100 - 18
    consume_txns = db.scalars(
        select(PackagingStockTxn).where(PackagingStockTxn.txn_type == "consume")
    ).all()
    assert len(consume_txns) == 6


def test_stocktake_writes_delta(db) -> None:
    sku = _sku(db, "保温袋")
    purchase_in(db, store_id=STORE_ID, sku_id=int(sku.id), qty=20, operator="tester", remark=None, biz_date=DAY)
    rows = stocktake(
        db,
        store_id=STORE_ID,
        lines=[(int(sku.id), 17)],
        operator="tester",
        biz_date=DAY,
    )
    assert rows[0]["delta"] == -3
    assert _qty(db, sku.id) == 17
    txn = db.scalar(
        select(PackagingStockTxn)
        .where(PackagingStockTxn.sku_id == int(sku.id), PackagingStockTxn.txn_type == "stocktake")
    )
    assert txn is not None
    assert int(txn.qty_delta) == -3


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    ensure_packaging_schema(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _sku(db, name: str, *, bag: bool = False) -> PackagingSku:
    row = PackagingSku(
        store_id=STORE_ID,
        name=name,
        unit="个",
        bag_flag=BAG_FLAG if bag else None,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _qty(db, sku_id: int) -> int:
    stock = db.get(PackagingStock, int(sku_id))
    return int(stock.qty) if stock is not None else 0
