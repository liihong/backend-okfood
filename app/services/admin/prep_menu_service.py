"""开菜单估算与食材、配菜维护。

重量：单份克数是毛菜。净菜克 = 毛菜克 × 出成率。斤 = 克 / 500。
先按克保留完整精度相加，最后再换算成斤并保留两位小数。
按个计的配菜只乘份数，不换算成斤，也不乘出成率。
份数覆盖只用于本次响应，不写回周菜单。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dish_prep_sop_line import DishPrepSopLine
from app.models.menu_dish import MenuDish
from app.models.prep_ingredient import PrepIngredient
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.schemas.prep_menu import (
    DishPrepSopLineOut,
    DishPrepSopOut,
    DishPrepSopPutIn,
    PrepEstimateDayOut,
    PrepEstimateIn,
    PrepEstimateLineOut,
    PrepEstimateOut,
    PrepIngredientIn,
    PrepIngredientOut,
    PrepIngredientPatchIn,
    PrepIngredientSummaryOut,
    PrepMealEstimateOut,
)

GRAMS_PER_JIN = Decimal("500")
QTY_STEP = Decimal("0.001")
RATE_STEP = Decimal("0.0001")
JIN_STEP = Decimal("0.01")
WEEKDAY_LABELS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
MEAL_ORDER = ("lunch", "dinner")


@dataclass(frozen=True)
class SopLineCalcIn:
    """参与纯计算的一行配菜。"""

    ingredient_id: int
    name: str
    unit: str
    gross_qty_per_portion: Decimal
    yield_rate: Decimal


@dataclass(frozen=True)
class SlotInput:
    """某一餐段某一天的排菜与日总份。没有槽位时不要传入。"""

    meal_period: str
    slot: int
    dish_id: int | None
    dish_name: str | None
    total_stock: int | None


@dataclass(frozen=True)
class OverrideInput:
    """本次预估份数。portions 为 None 时这一天视为未填份数。"""

    meal_period: str
    slot: int
    portions: int | None


@dataclass
class _GramBucket:
    ingredient_id: int
    name: str
    unit: str
    gross_grams: Decimal
    net_grams: Decimal
    gross_count: Decimal


def monday_of_week(day: date) -> date:
    """把任意日期归一到当周周一。"""
    return day - timedelta(days=day.weekday())


def format_qty(value: Decimal) -> str:
    """数量去掉无意义的尾零，最多保留 3 位小数。"""
    quantized = value.quantize(QTY_STEP, rounding=ROUND_HALF_UP)
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_rate(value: Decimal) -> str:
    """出成率固定 4 位小数，避免 0.7 在 JSON 数字里漂移。"""
    return format(value.quantize(RATE_STEP, rounding=ROUND_HALF_UP), "f")


def format_jin_from_grams(grams: Decimal) -> str:
    """克换算成斤，保留 2 位小数。0.01 斤 = 5 克。"""
    jin = (grams / GRAMS_PER_JIN).quantize(JIN_STEP, rounding=ROUND_HALF_UP)
    return format(jin, "f")


def _as_decimal(value: Decimal | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _line_amounts(line: SopLineCalcIn, portions: int) -> tuple[PrepEstimateLineOut, _GramBucket]:
    """算出一行的展示值和未舍入的克/个数，供汇总继续相加。"""
    if line.unit not in ("g", "piece"):
        raise ValueError(f"未知食材单位：{line.unit}")
    total = Decimal(portions) * _as_decimal(line.gross_qty_per_portion)
    per_text = format_qty(_as_decimal(line.gross_qty_per_portion))
    if line.unit == "piece":
        shown = PrepEstimateLineOut(
            ingredient_id=line.ingredient_id,
            name=line.name,
            unit="piece",
            per_portion_gross=per_text,
            yield_rate=None,
            gross_jin=None,
            net_jin=None,
            gross_count=format_qty(total),
        )
        bucket = _GramBucket(
            ingredient_id=line.ingredient_id,
            name=line.name,
            unit="piece",
            gross_grams=Decimal("0"),
            net_grams=Decimal("0"),
            gross_count=total,
        )
        return shown, bucket
    rate = _as_decimal(line.yield_rate)
    net = total * rate
    shown = PrepEstimateLineOut(
        ingredient_id=line.ingredient_id,
        name=line.name,
        unit="g",
        per_portion_gross=per_text,
        yield_rate=format_rate(rate),
        gross_jin=format_jin_from_grams(total),
        net_jin=format_jin_from_grams(net),
        gross_count=None,
    )
    bucket = _GramBucket(
        ingredient_id=line.ingredient_id,
        name=line.name,
        unit="g",
        gross_grams=total,
        net_grams=net,
        gross_count=Decimal("0"),
    )
    return shown, bucket


def _add_bucket(buckets: dict[int, _GramBucket], incoming: _GramBucket) -> None:
    current = buckets.get(incoming.ingredient_id)
    if current is None:
        buckets[incoming.ingredient_id] = _GramBucket(
            ingredient_id=incoming.ingredient_id,
            name=incoming.name,
            unit=incoming.unit,
            gross_grams=incoming.gross_grams,
            net_grams=incoming.net_grams,
            gross_count=incoming.gross_count,
        )
        return
    current.gross_grams += incoming.gross_grams
    current.net_grams += incoming.net_grams
    current.gross_count += incoming.gross_count


def _summary_from_buckets(buckets: dict[int, _GramBucket]) -> list[PrepIngredientSummaryOut]:
    """克数全部加完后再换算成斤，避免逐行四舍五入后再相加。"""
    rows: list[PrepIngredientSummaryOut] = []
    for bucket in buckets.values():
        if bucket.unit == "piece":
            if bucket.gross_count == 0:
                continue
            rows.append(
                PrepIngredientSummaryOut(
                    ingredient_id=bucket.ingredient_id,
                    name=bucket.name,
                    unit="piece",
                    gross_count=format_qty(bucket.gross_count),
                )
            )
            continue
        if bucket.gross_grams == 0 and bucket.net_grams == 0:
            continue
        rows.append(
            PrepIngredientSummaryOut(
                ingredient_id=bucket.ingredient_id,
                name=bucket.name,
                unit="g",
                gross_jin=format_jin_from_grams(bucket.gross_grams),
                net_jin=format_jin_from_grams(bucket.net_grams),
            )
        )
    rows.sort(key=lambda item: (0 if item.unit == "g" else 1, item.name, item.ingredient_id))
    return rows


def build_week_estimate(
    week_start: date,
    slots: list[SlotInput],
    sop_by_dish: dict[int, list[SopLineCalcIn]],
    overrides: list[OverrideInput],
) -> PrepEstimateOut:
    """按周一和已排菜估算整周。不读库，便于单测。"""
    anchor = monday_of_week(week_start)
    slot_map = {(row.meal_period, row.slot): row for row in slots}
    override_map = {(row.meal_period, row.slot): row.portions for row in overrides}
    meals: list[PrepMealEstimateOut] = []
    week_buckets: dict[int, _GramBucket] = {}
    for period in MEAL_ORDER:
        days: list[PrepEstimateDayOut] = []
        meal_buckets: dict[int, _GramBucket] = {}
        for slot in range(1, 8):
            day = _build_day(
                anchor=anchor,
                period=period,
                slot=slot,
                slot_row=slot_map.get((period, slot)),
                override_portions=override_map.get((period, slot), "absent"),
                sop_by_dish=sop_by_dish,
                meal_buckets=meal_buckets,
                week_buckets=week_buckets,
            )
            days.append(day)
        meals.append(
            PrepMealEstimateOut(
                meal_period=period,  # type: ignore[arg-type]
                days=days,
                ingredient_summary=_summary_from_buckets(meal_buckets),
            )
        )
    return PrepEstimateOut(
        week_start=anchor.isoformat(),
        meals=meals,
        week_ingredient_summary=_summary_from_buckets(week_buckets),
    )


def _build_day(
    *,
    anchor: date,
    period: str,
    slot: int,
    slot_row: SlotInput | None,
    override_portions: int | None | str,
    sop_by_dish: dict[int, list[SopLineCalcIn]],
    meal_buckets: dict[int, _GramBucket],
    week_buckets: dict[int, _GramBucket],
) -> PrepEstimateDayOut:
    menu_date = anchor + timedelta(days=slot - 1)
    base = dict(
        slot=slot,
        weekday=WEEKDAY_LABELS[slot - 1],
        menu_date=menu_date.isoformat(),
    )
    dish_id = slot_row.dish_id if slot_row is not None else None
    dish_name = slot_row.dish_name if slot_row is not None else None
    if dish_id is None:
        return PrepEstimateDayOut(
            **base,
            dish_id=None,
            dish_name=None,
            portions=None,
            portions_source="missing",
            status="no_dish",
            has_sop=False,
            lines=[],
        )
    sop_lines = sop_by_dish.get(int(dish_id), [])
    has_sop = len(sop_lines) > 0
    if override_portions != "absent":
        portions = override_portions if isinstance(override_portions, int) else None
        source = "override" if portions is not None else "missing"
    else:
        portions = slot_row.total_stock if slot_row is not None else None
        source = "total_stock" if portions is not None else "missing"
    if portions is None:
        return PrepEstimateDayOut(
            **base,
            dish_id=int(dish_id),
            dish_name=dish_name,
            portions=None,
            portions_source="missing",
            status="no_portions",
            has_sop=has_sop,
            lines=[],
        )
    if not has_sop:
        return PrepEstimateDayOut(
            **base,
            dish_id=int(dish_id),
            dish_name=dish_name,
            portions=portions,
            portions_source=source,  # type: ignore[arg-type]
            status="no_sop",
            has_sop=False,
            lines=[],
        )
    shown_lines: list[PrepEstimateLineOut] = []
    for line in sop_lines:
        shown, bucket = _line_amounts(line, portions)
        shown_lines.append(shown)
        if portions > 0:
            _add_bucket(meal_buckets, bucket)
            _add_bucket(week_buckets, bucket)
    return PrepEstimateDayOut(
        **base,
        dish_id=int(dish_id),
        dish_name=dish_name,
        portions=portions,
        portions_source=source,  # type: ignore[arg-type]
        status="ok",
        has_sop=True,
        lines=shown_lines,
    )


def _ingredient_out(row: PrepIngredient) -> PrepIngredientOut:
    unit = row.unit if row.unit in ("g", "piece") else "g"
    return PrepIngredientOut(
        id=int(row.id),
        name=row.name,
        unit=unit,  # type: ignore[arg-type]
        yield_rate=format_rate(_as_decimal(row.yield_rate)),
    )


def list_prep_ingredients(db: Session, *, store_id: int) -> list[PrepIngredientOut]:
    rows = db.scalars(
        select(PrepIngredient)
        .where(PrepIngredient.store_id == int(store_id))
        .order_by(PrepIngredient.name.asc(), PrepIngredient.id.asc())
    ).all()
    return [_ingredient_out(row) for row in rows]


def _name_taken(db: Session, *, store_id: int, name: str, exclude_id: int | None) -> bool:
    stmt = select(PrepIngredient.id).where(
        PrepIngredient.store_id == int(store_id),
        PrepIngredient.name == name,
    )
    if exclude_id is not None:
        stmt = stmt.where(PrepIngredient.id != int(exclude_id))
    return db.scalar(stmt) is not None


def create_prep_ingredient(db: Session, body: PrepIngredientIn, *, store_id: int) -> PrepIngredientOut:
    sid = int(store_id)
    if _name_taken(db, store_id=sid, name=body.name, exclude_id=None):
        raise HTTPException(status_code=409, detail="同名食材已存在")
    row = PrepIngredient(
        store_id=sid,
        name=body.name,
        unit=body.unit,
        yield_rate=body.yield_rate,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="同名食材已存在")
    db.refresh(row)
    return _ingredient_out(row)


def _get_ingredient(db: Session, ingredient_id: int, *, store_id: int) -> PrepIngredient:
    row = db.get(PrepIngredient, int(ingredient_id))
    if row is None or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="食材不存在")
    return row


def patch_prep_ingredient(
    db: Session, ingredient_id: int, body: PrepIngredientPatchIn, *, store_id: int
) -> PrepIngredientOut:
    row = _get_ingredient(db, ingredient_id, store_id=store_id)
    if body.name is not None and body.name != row.name:
        if _name_taken(db, store_id=store_id, name=body.name, exclude_id=int(row.id)):
            raise HTTPException(status_code=409, detail="同名食材已存在")
        row.name = body.name
    if body.unit is not None:
        row.unit = body.unit
    if row.unit == "piece":
        row.yield_rate = Decimal("1")
    elif body.yield_rate is not None:
        row.yield_rate = body.yield_rate
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="同名食材已存在")
    db.refresh(row)
    return _ingredient_out(row)


def delete_prep_ingredient(db: Session, ingredient_id: int, *, store_id: int) -> None:
    row = _get_ingredient(db, ingredient_id, store_id=store_id)
    used = db.scalar(
        select(func.count())
        .select_from(DishPrepSopLine)
        .where(DishPrepSopLine.ingredient_id == int(row.id))
    )
    if used:
        raise HTTPException(status_code=400, detail="该食材已用于菜品配方，不能删除")
    db.delete(row)
    db.commit()


def _get_store_dish(db: Session, dish_id: int, *, store_id: int) -> MenuDish:
    dish = db.get(MenuDish, int(dish_id))
    if dish is None or int(dish.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="菜品不存在")
    return dish


def get_dish_prep_sop(db: Session, dish_id: int, *, store_id: int) -> DishPrepSopOut:
    dish = _get_store_dish(db, dish_id, store_id=store_id)
    return _sop_out(db, dish, store_id=int(store_id))


def _sop_out(db: Session, dish: MenuDish, *, store_id: int) -> DishPrepSopOut:
    rows = db.execute(
        select(DishPrepSopLine, PrepIngredient)
        .join(PrepIngredient, PrepIngredient.id == DishPrepSopLine.ingredient_id)
        .where(
            DishPrepSopLine.store_id == int(store_id),
            DishPrepSopLine.dish_id == int(dish.id),
        )
        .order_by(DishPrepSopLine.sort_order.asc(), DishPrepSopLine.id.asc())
    ).all()
    lines: list[DishPrepSopLineOut] = []
    for sop, ingredient in rows:
        unit = ingredient.unit if ingredient.unit in ("g", "piece") else "g"
        lines.append(
            DishPrepSopLineOut(
                ingredient_id=int(ingredient.id),
                name=ingredient.name,
                unit=unit,  # type: ignore[arg-type]
                yield_rate=format_rate(_as_decimal(ingredient.yield_rate)),
                gross_qty_per_portion=format_qty(_as_decimal(sop.gross_qty_per_portion)),
                sort_order=int(sop.sort_order),
            )
        )
    return DishPrepSopOut(dish_id=int(dish.id), dish_name=dish.name, lines=lines)


def replace_dish_prep_sop(
    db: Session, dish_id: int, body: DishPrepSopPutIn, *, store_id: int
) -> DishPrepSopOut:
    """整单覆盖配菜。只写配菜表，不改菜品说明和周菜单。"""
    sid = int(store_id)
    dish = _get_store_dish(db, dish_id, store_id=sid)
    ingredient_ids = [line.ingredient_id for line in body.lines]
    if ingredient_ids:
        found = db.scalars(
            select(PrepIngredient).where(
                PrepIngredient.store_id == sid,
                PrepIngredient.id.in_(ingredient_ids),
            )
        ).all()
        found_ids = {int(row.id) for row in found}
        missing = [item for item in ingredient_ids if item not in found_ids]
        if missing:
            raise HTTPException(status_code=400, detail="食材不存在")
    db.execute(
        delete(DishPrepSopLine).where(
            DishPrepSopLine.store_id == sid,
            DishPrepSopLine.dish_id == int(dish.id),
        )
    )
    for index, line in enumerate(body.lines):
        db.add(
            DishPrepSopLine(
                store_id=sid,
                dish_id=int(dish.id),
                ingredient_id=int(line.ingredient_id),
                gross_qty_per_portion=line.gross_qty_per_portion,
                sort_order=index,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="保存配菜失败，请检查食材是否重复或已删除")
    return _sop_out(db, dish, store_id=sid)


def estimate_prep_menu(db: Session, body: PrepEstimateIn, *, store_id: int) -> PrepEstimateOut:
    """按本周已排菜和日总份估算。份数覆盖不落库。"""
    sid = int(store_id)
    anchor = monday_of_week(body.week_start)
    slot_rows = db.scalars(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
        )
    ).all()
    dish_ids = sorted({int(row.dish_id) for row in slot_rows})
    dish_name: dict[int, str] = {}
    if dish_ids:
        dishes = db.scalars(
            select(MenuDish).where(MenuDish.store_id == sid, MenuDish.id.in_(dish_ids))
        ).all()
        dish_name = {int(row.id): row.name for row in dishes}
    sop_by_dish = _load_sop(db, store_id=sid, dish_ids=dish_ids)
    slots = [
        SlotInput(
            meal_period=row.meal_period,
            slot=int(row.slot),
            dish_id=int(row.dish_id) if int(row.dish_id) in dish_name else None,
            dish_name=dish_name.get(int(row.dish_id)),
            total_stock=int(row.total_stock) if row.total_stock is not None else None,
        )
        for row in slot_rows
        if row.meal_period in MEAL_ORDER and 1 <= int(row.slot) <= 7
    ]
    overrides = [
        OverrideInput(meal_period=item.meal_period, slot=item.slot, portions=item.portions)
        for item in body.portion_overrides
    ]
    return build_week_estimate(anchor, slots, sop_by_dish, overrides)


def _load_sop(db: Session, *, store_id: int, dish_ids: list[int]) -> dict[int, list[SopLineCalcIn]]:
    if not dish_ids:
        return {}
    rows = db.execute(
        select(DishPrepSopLine, PrepIngredient)
        .join(PrepIngredient, PrepIngredient.id == DishPrepSopLine.ingredient_id)
        .where(
            DishPrepSopLine.store_id == int(store_id),
            DishPrepSopLine.dish_id.in_(dish_ids),
            PrepIngredient.store_id == int(store_id),
        )
        .order_by(DishPrepSopLine.sort_order.asc(), DishPrepSopLine.id.asc())
    ).all()
    grouped: dict[int, list[SopLineCalcIn]] = {}
    for sop, ingredient in rows:
        grouped.setdefault(int(sop.dish_id), []).append(
            SopLineCalcIn(
                ingredient_id=int(ingredient.id),
                name=ingredient.name,
                unit=ingredient.unit,
                gross_qty_per_portion=_as_decimal(sop.gross_qty_per_portion),
                yield_rate=_as_decimal(ingredient.yield_rate),
            )
        )
    return grouped
