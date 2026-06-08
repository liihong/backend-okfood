"""小程序首页 Banner 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


LINK_TYPES = frozenset({"none", "dish", "tab", "webview", "member_card"})


class HomeBannerOut(BaseModel):
    id: int
    store_id: int
    title: str | None = None
    image_url: str
    link_type: str
    link_target: str | None = None
    sort_order: int = 0
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class HomeBannerPublicOut(BaseModel):
    id: int
    image_url: str
    link_type: str
    link_target: str | None = None


class HomeBannerCreateIn(BaseModel):
    title: str | None = Field(None, max_length=128)
    image_url: str = Field(..., min_length=1)
    link_type: str = Field(default="none", max_length=32)
    link_target: str | None = Field(None, max_length=512)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


class HomeBannerPatchIn(BaseModel):
    title: str | None = Field(None, max_length=128)
    image_url: str | None = Field(None, min_length=1)
    link_type: str | None = Field(None, max_length=32)
    link_target: str | None = Field(None, max_length=512)
    sort_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class HomeBannerActiveIn(BaseModel):
    is_active: bool
