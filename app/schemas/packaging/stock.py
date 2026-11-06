"""入库、校对和流水查询入参。"""

from datetime import date

from pydantic import BaseModel, Field


class PackagingPurchaseIn(BaseModel):
    sku_id: int = Field(..., ge=1)
    qty: int = Field(..., ge=1)
    remark: str | None = Field(None, max_length=200)
    biz_date: date | None = None


class PackagingStocktakeLineIn(BaseModel):
    sku_id: int = Field(..., ge=1)
    actual_qty: int = Field(..., ge=0)


class PackagingStocktakeIn(BaseModel):
    lines: list[PackagingStocktakeLineIn] = Field(..., min_length=1)
    biz_date: date | None = None
