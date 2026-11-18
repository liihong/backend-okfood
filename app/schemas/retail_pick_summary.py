"""管理端：商城订单 SKU 备货汇总（厨师看板）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetailPickSummarySkuOut(BaseModel):
    """单个 SKU 在待备货队列中的盒数汇总。"""

    retail_product_id: int
    display_title: str
    spu_title: str | None = None
    spec_label: str | None = None
    sku_code: str | None = None
    category_id: int | None = None
    total_boxes: int = Field(..., ge=0)
    order_count: int = Field(..., ge=0)
    pickup_boxes: int = Field(0, ge=0)
    delivery_boxes: int = Field(0, ge=0)


class RetailPickSummaryOut(BaseModel):
    """厨师看板汇总响应。"""

    scope_label: str = Field(
        default="已支付 · 已接单 · 待发货",
        description="与订单列表「待发货」Tab 口径一致",
    )
    order_count: int = Field(0, ge=0, description="纳入统计的订单笔数")
    sku_count: int = Field(0, ge=0)
    grand_total_boxes: int = Field(0, ge=0)
    items: list[RetailPickSummarySkuOut] = Field(default_factory=list)