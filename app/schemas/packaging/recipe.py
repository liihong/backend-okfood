"""菜品用盒、槽位用盒、每份标配入参。"""

from datetime import date

from pydantic import BaseModel, Field


class PackagingRecipeLineIn(BaseModel):
    sku_id: int = Field(..., ge=1)
    qty_per_portion: int = Field(..., ge=1)


class PackagingRecipeReplaceIn(BaseModel):
    lines: list[PackagingRecipeLineIn] = Field(default_factory=list)


class PackagingSlotRecipeIn(BaseModel):
    week_start: date
    slot: int = Field(..., ge=1, le=7)
    meal_period: str
    lines: list[PackagingRecipeLineIn] = Field(default_factory=list)
