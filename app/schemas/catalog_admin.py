"""后台：会员卡模版与零售 SKU 的请求/响应模型。"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class MembershipCardTemplateOut(BaseModel):
    id: int
    tenant_id: int
    kind_label: str = Field(..., description="种类：手填，如 周卡/季卡/午晚餐卡")
    period_kind: str | None = Field(None, description="可选占位 weekly|monthly，后续自动化可用")
    meal_periods: list[str] = Field(
        default_factory=lambda: ["lunch"],
        description='覆盖餐段：["lunch"] / ["dinner"] / ["lunch","dinner"]',
    )
    deliver_dinner_with_lunch: bool = Field(
        False,
        description="午+晚卡是否与午餐一起配送（午餐送达时同时扣晚餐）；只勾单餐段时忽略",
    )
    name: str
    meals_grant: int
    list_price_yuan: str | None = Field(None, description="原价（划线价），可为空")
    sale_price_yuan: str | None = Field(None, description="优惠价（展示）；自助支付仍以门店周/月卡配置为准")
    card_style_image_url: str | None = Field(None, description="卡片样式图，小程序展示")
    validity_days: int | None = Field(None, description="有效天数（展示）")
    intro_short: str | None = Field(None, description="商品简介")
    purchase_notice: str | None = Field(None, description="购买须知")
    remark: str | None
    sort_order: int
    is_active: bool


class MembershipCardTemplateCreateIn(BaseModel):
    kind_label: str = Field(..., min_length=1, max_length=64, description="种类，自由填写")
    name: str = Field(..., min_length=1, max_length=128)
    meals_grant: int = Field(..., ge=1, le=366)
    list_price_yuan: Decimal | None = Field(
        None, ge=Decimal("0"), max_digits=12, decimal_places=2, description="原价（划线价）"
    )
    sale_price_yuan: Decimal | None = Field(
        None, ge=Decimal("0"), max_digits=12, decimal_places=2, description="优惠价"
    )
    card_style_image_url: str | None = Field(None, max_length=512)
    validity_days: int | None = Field(None, ge=0, le=3660, description="有效天数（展示）")
    intro_short: str | None = Field(None, max_length=512)
    purchase_notice: str | None = Field(None, max_length=65535)
    remark: str | None = Field(None, max_length=4096)
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True
    meal_periods: list[str] = Field(
        default_factory=lambda: ["lunch"],
        description='覆盖餐段：["lunch"] / ["dinner"] / ["lunch","dinner"]',
    )
    deliver_dinner_with_lunch: bool = Field(
        False,
        description="午+晚卡是否与午餐一起配送；默认否（分开配送、各扣各的）",
    )


class MembershipCardTemplatePatchIn(BaseModel):
    kind_label: str | None = Field(None, min_length=1, max_length=64)
    name: str | None = Field(None, min_length=1, max_length=128)
    meals_grant: int | None = Field(None, ge=1, le=366)
    list_price_yuan: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    sale_price_yuan: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    card_style_image_url: str | None = Field(None, max_length=512)
    validity_days: int | None = Field(None, ge=0, le=3660)
    intro_short: str | None = Field(None, max_length=512)
    purchase_notice: str | None = Field(None, max_length=65535)
    remark: str | None = None
    sort_order: int | None = Field(None, ge=0)
    is_active: bool | None = None
    meal_periods: list[str] | None = Field(None, description="覆盖餐段")
    deliver_dinner_with_lunch: bool | None = Field(
        None, description="午+晚是否与午餐一起配送；只勾单餐段时服务端强制 false"
    )


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


class StoreRetailSpuOut(BaseModel):
    id: int
    store_id: int
    category_id: int | None
    title: str
    subtitle: str | None
    detail_html: str | None
    gallery_urls: list[str] = Field(default_factory=list)
    cover_image_url: str | None = None
    purchase_notice: str | None = None
    sort_order: int
    is_on_shelf: bool
    sku_count: int = 0
    price_min_yuan: str | None = None
    price_max_yuan: str | None = None
    skus: list["StoreRetailSkuOut"] = Field(default_factory=list)


class StoreRetailSpuCreateIn(BaseModel):
    category_id: int | None = None
    title: str = Field(..., min_length=1, max_length=256)
    subtitle: str | None = Field(None, max_length=512)
    detail_html: str | None = Field(None, max_length=65535)
    gallery_urls: list[str] | None = Field(None, description="轮播图 URL 列表")
    purchase_notice: str | None = Field(None, max_length=65535)
    sort_order: int = Field(default=0, ge=0)
    is_on_shelf: bool = False


class StoreRetailSpuPatchIn(BaseModel):
    category_id: int | None = None
    title: str | None = Field(None, min_length=1, max_length=256)
    subtitle: str | None = Field(None, max_length=512)
    detail_html: str | None = None
    gallery_urls: list[str] | None = None
    purchase_notice: str | None = None
    sort_order: int | None = Field(None, ge=0)
    is_on_shelf: bool | None = None


class StoreRetailSkuOut(BaseModel):
    id: int
    store_id: int
    spu_id: int
    sku_code: str | None
    spec_label: str | None
    unit_price_yuan: str
    list_price_yuan: str | None
    sort_order: int
    is_on_shelf: bool
    stock_quantity: int | None = Field(None, description="库存上限；空=不限")
    sold_count: int = Field(0, description="已售件数（已支付）")
    stock_remaining: int | None = Field(None, description="剩余可售；空=不限")
    spu_title: str | None = None
    display_title: str | None = None


class StoreRetailSkuCreateIn(BaseModel):
    spu_id: int = Field(..., ge=1)
    sku_code: str | None = Field(None, max_length=64)
    spec_label: str | None = Field(None, max_length=128)
    unit_price_yuan: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    list_price_yuan: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    sort_order: int = Field(default=0, ge=0)
    is_on_shelf: bool = False
    stock_quantity: int | None = Field(None, ge=0, le=999999, description="库存上限；空=不限")


class StoreRetailSkuPatchIn(BaseModel):
    spu_id: int | None = Field(None, ge=1)
    sku_code: str | None = Field(None, max_length=64)
    spec_label: str | None = Field(None, max_length=128)
    unit_price_yuan: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    list_price_yuan: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    sort_order: int | None = Field(None, ge=0)
    is_on_shelf: bool | None = None
    stock_quantity: int | None = Field(None, ge=0, le=999999, description="库存上限；空=不限")


class StoreRetailSkuUpsertIn(BaseModel):
    """保存商品 bundle 时的 SKU 行（新建 id 为空）。"""

    id: int | None = Field(None, ge=1, description="已有 SKU id；新建留空")
    sku_code: str | None = Field(None, max_length=64)
    spec_label: str | None = Field(None, max_length=128)
    unit_price_yuan: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    list_price_yuan: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    sort_order: int = Field(default=0, ge=0)
    is_on_shelf: bool = False
    stock_quantity: int | None = Field(None, ge=0, le=999999)


class StoreRetailSpuBundleSaveIn(BaseModel):
    """原子保存：SPU + 至少一个 SKU。"""

    category_id: int | None = None
    title: str = Field(..., min_length=1, max_length=256)
    subtitle: str | None = Field(None, max_length=512)
    detail_html: str | None = Field(None, max_length=65535)
    gallery_urls: list[str] | None = None
    purchase_notice: str | None = Field(None, max_length=65535)
    sort_order: int = Field(default=0, ge=0)
    is_on_shelf: bool = False
    skus: list[StoreRetailSkuUpsertIn] = Field(..., min_length=1, max_length=50)


# 兼容旧命名：retail_product = SKU
StoreRetailProductOut = StoreRetailSkuOut
StoreRetailProductCreateIn = StoreRetailSkuCreateIn
StoreRetailProductPatchIn = StoreRetailSkuPatchIn
