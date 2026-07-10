from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StoreRetailOrderCreateIn(BaseModel):
    retail_product_id: int = Field(..., ge=1)
    member_address_id: int | None = Field(
        default=None,
        ge=1,
        description="配送到家时必填；门店自提勿传",
    )
    store_pickup: bool = Field(False, description="门店自提")
    quantity: int = Field(1, ge=1, le=50)
    member_coupon_id: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def _address_when_delivery(self) -> "StoreRetailOrderCreateIn":
        if not self.store_pickup and self.member_address_id is None:
            raise ValueError("配送到家须选择配送地址")
        return self


class StoreRetailOrderOut(BaseModel):
    id: int
    out_trade_no: str = ""
    retail_product_id: int
    product_title: str
    member_address_id: int | None = None
    store_pickup: bool = False
    quantity: int = 1
    fulfillment_date: date
    routing_area: str
    amount_yuan: str
    original_amount_yuan: str | None = None
    coupon_discount_yuan: str | None = None
    member_coupon_id: int | None = None
    pay_status: str
    pay_channel: str | None = None
    fulfillment_status: str
    courier_id: str | None = None
    sf_same_city_push_id: int | None = None
    sf_order_id: str | None = None
    address_summary: str
    store_contact_phone: str | None = None
    created_at: datetime | None = None


class AdminStoreRetailOrderListOut(StoreRetailOrderOut):
    member_id: int
    member_phone: str = ""
    member_name: str = ""
    recipient_contact_name: str = ""
    address_remarks: str = ""
    remark: str | None = None


class StoreRetailOrderRemarkPatchIn(BaseModel):
    """管理端：更新商城订单后台备注。"""

    remark: str | None = Field(None, max_length=500)


class StoreRetailOrderDeliveryPatchIn(BaseModel):
    """管理端：修改商城订单配送方式与收货地址。"""

    store_pickup: bool = Field(..., description="true=门店自提；false=配送到家")
    member_address_id: int | None = Field(
        None,
        ge=1,
        description="配送到家时必填：会员已保存的配送地址 id；门店自提勿传",
    )

    @model_validator(mode="after")
    def _address_when_delivery(self) -> "StoreRetailOrderDeliveryPatchIn":
        if not self.store_pickup and self.member_address_id is None:
            raise ValueError("配送到家须选择配送地址")
        return self


class StoreRetailOrderMemberAddressPatchIn(BaseModel):
    """会员端：待接单状态下修改配送到家收货地址。"""

    member_address_id: int = Field(..., ge=1, description="会员已保存的配送地址 id")


class StoreRetailOrderIdsIn(BaseModel):
    order_ids: list[int] = Field(..., min_length=1, max_length=100)


class StoreRetailAssignCourierIn(BaseModel):
    courier_id: str = Field(..., min_length=1, max_length=50)


class StoreRetailBatchAssignCourierIn(BaseModel):
    order_ids: list[int] = Field(..., min_length=1, max_length=100)
    courier_id: str = Field(..., min_length=1, max_length=50)


class StoreRetailCancelIn(BaseModel):
    cancel_reason: str | None = Field(None, max_length=200)
    cancel_sf: bool = Field(True, description="若已推顺丰则同步请求取消")


class AdminStoreRetailOrderCreateIn(BaseModel):
    """管理端：手动创建商城零售订单。"""

    phone: str = Field(..., min_length=5, max_length=20, description="会员手机号")
    name: str | None = Field(
        None,
        max_length=100,
        description="会员不存在时须填写姓名以创建新会员",
    )
    retail_product_id: int = Field(..., ge=1, description="商城商品 id")
    quantity: int = Field(1, ge=1, le=50)
    store_pickup: bool = Field(False, description="门店自提")
    member_address_id: int | None = Field(
        None,
        ge=1,
        description="配送到家时必填：会员已保存的配送地址 id",
    )
    pay_channel: Literal["微信", "线下", "抖音"] = Field(..., description="支付渠道")
    pay_status: Literal["已支付", "未支付"] = Field("已支付", description="支付状态")
    amount_yuan: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        description="实收金额；空则按商品售价与配送方式自动计算",
    )
    remark: str | None = Field(None, max_length=500, description="后台备注")

    @model_validator(mode="after")
    def _address_when_delivery(self) -> "AdminStoreRetailOrderCreateIn":
        if not self.store_pickup and self.member_address_id is None:
            raise ValueError("配送到家须选择配送地址")
        return self
