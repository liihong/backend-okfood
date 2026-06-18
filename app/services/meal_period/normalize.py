"""餐段归一化：未传参时默认午餐（兼容现网午餐链路）；非法值必须报错，禁止静默当成午餐。"""

from __future__ import annotations

from fastapi import HTTPException

from app.models.enums import MealPeriod
from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD


def normalize_meal_period(meal_period: str | None) -> str:
    """
    将 meal_period 规范为 lunch / dinner。

    - None 或空字符串：回落 DEFAULT_MEAL_PERIOD（午餐），保持现网午餐默认行为。
    - 非法值（如 dinnerx、空格外误传）：HTTP 400，禁止静默写入午餐槽位以免误导营业数据。
    """
    p = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    if p not in (MealPeriod.LUNCH.value, MealPeriod.DINNER.value):
        raise HTTPException(
            status_code=400,
            detail="meal_period 须为 lunch（午餐）或 dinner（晚餐）",
        )
    return p
