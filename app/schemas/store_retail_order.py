from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StoreRetailOrderItemIn(BaseModel):
    """商城下单单行。"""

    retail_product_id: int = Field(..., ge=1)
    quantity: int = Field(1, ge=1, le=50)


class StoreRetailOrderItemOut(BaseModel):
    id: int
    retail_product_id: int
    spu_id: int | None = None
    product_title: str
    spu_title: str | None = None
    spec_label: str | None = None
    unit_price_yuan: str
    quantity: int
    line_amount_yuan: str
    category_id: int | None = None


class StoreRetailOrderCreateIn(BaseModel):
    """商城购物车结算：多 SKU。"""

    items: list[StoreRetailOrderItemIn] = Field(..., min_length=1, max_length=20)
    member_address_id: int | None = Field(
        default=None,
        ge=1,
        description="配送到家时必填；门店自提勿传",
    )
    store_pickup: bool = Field(False, description="门店自提")
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
    item_count: int = 1
    items: list[StoreRetailOrderItemOut] = Field(default_factory=list)
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


class AdminRetailDeliveryAddressIn(BaseModel):
    """管理端手动建单：当场登记商城收货地址（写入 retail 用途，不改会员送餐地址）。"""

    contact_name: str | None = Field(None, max_length=100, description="收件人；空则用会员姓名")
    contact_phone: str | None = Field(None, max_length=20, description="收货电话；空则用会员手机号")
    lng: float = Field(..., ge=-180, le=180, description="GCJ-02 经度（高德）")
    lat: float = Field(..., ge=-90, le=90, description="GCJ-02 纬度（高德）")
    map_location_text: str = Field(..., min_length=1, max_length=500)
    door_detail: str | None = Field(None, max_length=500)
    remarks: str | None = Field(None, max_length=500)


class AdminStoreRetailOrderCreateIn(BaseModel):
    """管理端：手动创建商城零售订单（支持多 SKU）。"""

    phone: str = Field(..., min_length=5, max_length=20, description="会员手机号")
    name: str | None = Field(
        None,
        max_length=100,
        description="会员不存在时须填写姓名以创建新会员",
    )
    items: list[StoreRetailOrderItemIn] = Field(..., min_length=1, max_length=20)
    store_pickup: bool = Field(False, description="门店自提")
    member_address_id: int | None = Field(
        None,
        ge=1,
        description="配送到家：选用已有地址；与 delivery_address 二选一",
    )
    delivery_address: AdminRetailDeliveryAddressIn | None = Field(
        None,
        description="配送到家：当场登记商城收货地址；与 member_address_id 二选一",
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
        if self.store_pickup:
            return self
        if self.member_address_id is None and self.delivery_address is None:
            raise ValueError("配送到家须选择已有地址或登记新的收货地址")
        return self
