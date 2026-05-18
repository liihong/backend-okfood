"""后台：会员卡模版与零售 SKU 的请求/响应模型。"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class MembershipCardTemplateOut(BaseModel):
    id: int
    store_id: int
    tenant_id: int
    kind_label: str = Field(..., description="种类：手填，如 周卡/季卡/午晚餐卡")
    period_kind: str | None = Field(None, description="可选占位 weekly|monthly，后续自动化可用")
    name: str
    meals_grant: int
    remark: str | None
    sort_order: int
    is_active: bool


class MembershipCardTemplateCreateIn(BaseModel):
    kind_label: str = Field(..., min_length=1, max_length=64, description="种类，自由填写")
    name: str = Field(..., min_length=1, max_length=128)
    meals_grant: int = Field(..., ge=1, le=366)
    remark: str | None = Field(None, max_length=4096)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


class MembershipCardTemplatePatchIn(BaseModel):
    kind_label: str | None = Field(None, min_length=1, max_length=64)
    name: str | None = Field(None, min_length=1, max_length=128)
    meals_grant: int | None = Field(None, ge=1, le=366)
    remark: str | None = None
    sort_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class StoreRetailCategoryOut(BaseModel):
    id: int
    store_id: int
    name: str
    sort_order: int
    is_active: bool


class StoreRetailCategoryCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


class StoreRetailCategoryPatchIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    sort_order: int | None = Field(None, ge=0)
    is_active: bool | None = None


class StoreRetailProductOut(BaseModel):
    id: int
    store_id: int
    category_id: int | None
    sku_code: str | None
    title: str
    subtitle: str | None
    description: str | None
    unit_price_yuan: str
    list_price_yuan: str | None
    cover_image_url: str | None
    sort_order: int
    is_on_shelf: bool


class StoreRetailProductCreateIn(BaseModel):
    category_id: int | None = None
    sku_code: str | None = Field(None, max_length=64)
    title: str = Field(..., min_length=1, max_length=256)
    subtitle: str | None = Field(None, max_length=512)
    description: str | None = Field(None, max_length=65535)
    unit_price_yuan: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    list_price_yuan: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    cover_image_url: str | None = Field(None, max_length=512)
    sort_order: int = Field(default=0, ge=0)
    is_on_shelf: bool = False


class StoreRetailProductPatchIn(BaseModel):
    category_id: int | None = None
    sku_code: str | None = Field(None, max_length=64)
    title: str | None = Field(None, min_length=1, max_length=256)
    subtitle: str | None = Field(None, max_length=512)
    description: str | None = None
    unit_price_yuan: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    list_price_yuan: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    cover_image_url: str | None = Field(None, max_length=512)
    sort_order: int | None = Field(None, ge=0)
    is_on_shelf: bool | None = None
