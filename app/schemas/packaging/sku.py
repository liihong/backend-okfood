"""包装品类入参。"""

from pydantic import BaseModel, Field


class PackagingSkuIn(BaseModel):
    name: str = Field(..., max_length=64)
    usage_note: str | None = Field(None, max_length=64)
    supplier_name: str | None = Field(None, max_length=64)
    unit: str = Field("个", max_length=16)
    safety_stock: int | None = Field(None, ge=0)
    is_meal_bag: bool = False


class PackagingSkuPatchIn(BaseModel):
    name: str | None = Field(None, max_length=64)
    usage_note: str | None = Field(None, max_length=64)
    supplier_name: str | None = Field(None, max_length=64)
    unit: str | None = Field(None, max_length=16)
    safety_stock: int | None = Field(None, ge=0)
    is_active: bool | None = None
    is_meal_bag: bool | None = None
