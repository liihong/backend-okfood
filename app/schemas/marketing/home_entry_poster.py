"""小程序进入弹窗海报请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HomeEntryPosterOut(BaseModel):
    id: int
    store_id: int
    image_url: str
    is_active: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class HomeEntryPosterPublicOut(BaseModel):
    image_url: str


class HomeEntryPosterUpsertIn(BaseModel):
    image_url: str = Field(..., min_length=1)
    is_active: bool = False
