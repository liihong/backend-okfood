"""随餐饮饮品的入参和出参。不放进菜品大 schema，避免和菜品字段缠在一起。"""

from pydantic import BaseModel, Field


class DrinkUpsertIn(BaseModel):
    """新建时省略 id；更新时带 id。"""

    id: int | None = Field(None, ge=1)
    name: str = Field(..., max_length=200)
    description: str | None = Field(None, max_length=1000)
    image_url: str | None = Field(None, max_length=2_000_000)
    is_enabled: bool = True


class DrinkAdminOut(BaseModel):
    id: int
    name: str
    description: str | None
    image_url: str | None
    is_enabled: bool
    created_at: str
