"""开菜单：食材、菜品配菜、按周估算。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

PrepUnit = Literal["g", "piece"]
PrepDayStatus = Literal["ok", "no_dish", "no_portions", "no_sop"]
PortionSource = Literal["total_stock", "override", "missing"]
MealPeriodCode = Literal["lunch", "dinner"]


def _clean_name(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("食材名称不能为空")
    return text


def _meal_period(value: str) -> str:
    period = (value or "").strip().lower()
    if period not in ("lunch", "dinner"):
        raise ValueError("meal_period 须为 lunch（午餐）或 dinner（晚餐）")
    return period


class PrepIngredientIn(BaseModel):
    """新建食材。按个计时出成率固定为 1，不参与斤的换算。"""

    name: str = Field(..., max_length=64)
    unit: PrepUnit
    yield_rate: Decimal = Field(default=Decimal("1"), gt=0, le=1, max_digits=6, decimal_places=4)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean_name(value)

    @model_validator(mode="after")
    def piece_yield_is_one(self) -> Self:
        if self.unit == "piece":
            self.yield_rate = Decimal("1")
        return self


class PrepIngredientPatchIn(BaseModel):
    """修改食材。未传的字段保持原值。"""

    name: str | None = Field(default=None, max_length=64)
    unit: PrepUnit | None = None
    yield_rate: Decimal | None = Field(default=None, gt=0, le=1, max_digits=6, decimal_places=4)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_name(value)


class PrepIngredientOut(BaseModel):
    id: int
    name: str
    unit: PrepUnit
    yield_rate: str


class DishPrepSopLineIn(BaseModel):
    """一行配菜。数量是单份毛菜。"""

    ingredient_id: int = Field(..., ge=1)
    gross_qty_per_portion: Decimal = Field(..., gt=0, le=Decimal("1000000"), max_digits=12, decimal_places=3)


class DishPrepSopPutIn(BaseModel):
    """整单覆盖该菜品的配菜。空列表表示清空。"""

    lines: list[DishPrepSopLineIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_ingredient(self) -> Self:
        ids = [line.ingredient_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("同一菜品不能重复添加同一食材")
        return self


class DishPrepSopLineOut(BaseModel):
    ingredient_id: int
    name: str
    unit: PrepUnit
    yield_rate: str
    gross_qty_per_portion: str
    sort_order: int


class DishPrepSopOut(BaseModel):
    dish_id: int
    dish_name: str
    lines: list[DishPrepSopLineOut]


class PortionOverrideIn(BaseModel):
    """本次预估份数。portions 为空表示这一天不估算，也不回读日总份。"""

    meal_period: str
    slot: int = Field(..., ge=1, le=7)
    portions: int | None = Field(default=None, ge=0, le=100000)

    @field_validator("meal_period")
    @classmethod
    def _period(cls, value: str) -> str:
        return _meal_period(value)


class PrepEstimateIn(BaseModel):
    week_start: date = Field(..., description="该周任意一天，服务端归一为周一")
    portion_overrides: list[PortionOverrideIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_override(self) -> Self:
        seen: set[tuple[str, int]] = set()
        for item in self.portion_overrides:
            key = (item.meal_period, item.slot)
            if key in seen:
                raise ValueError("同一餐段同一天的份数只能覆盖一次")
            seen.add(key)
        return self


class PrepEstimateLineOut(BaseModel):
    ingredient_id: int
    name: str
    unit: PrepUnit
    per_portion_gross: str
    yield_rate: str | None = None
    gross_jin: str | None = None
    net_jin: str | None = None
    gross_count: str | None = None


class PrepEstimateDayOut(BaseModel):
    slot: int
    weekday: str
    menu_date: str
    dish_id: int | None = None
    dish_name: str | None = None
    portions: int | None = None
    portions_source: PortionSource
    status: PrepDayStatus
    has_sop: bool
    lines: list[PrepEstimateLineOut]


class PrepIngredientSummaryOut(BaseModel):
    ingredient_id: int
    name: str
    unit: PrepUnit
    gross_jin: str | None = None
    net_jin: str | None = None
    gross_count: str | None = None


class PrepMealEstimateOut(BaseModel):
    meal_period: MealPeriodCode
    days: list[PrepEstimateDayOut]
    ingredient_summary: list[PrepIngredientSummaryOut]


class PrepEstimateOut(BaseModel):
    week_start: str
    meals: list[PrepMealEstimateOut]
    week_ingredient_summary: list[PrepIngredientSummaryOut]
