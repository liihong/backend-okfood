from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SingleMealOrderCreateIn(BaseModel):
    dish_id: int = Field(..., ge=1)
    member_address_id: int | None = Field(
        default=None,
        ge=1,
        description="配送到家时必填：会员已保存的配送地址 id；门店自提勿传",
    )
    delivery_date: date = Field(..., description="与周菜单该道菜对应的供餐日")
    meal_period: str = Field("lunch", description="lunch=午餐单次；dinner=晚餐单次")
    store_pickup: bool = Field(False, description="门店自提：无需地址，支付后为待自提，门店确认取货后完成")
    quantity: int = Field(1, ge=1, le=50, description="份数，总价=单价×份数")
    member_coupon_id: int | None = Field(None, ge=1, description="可选：使用的用户优惠券 id")

    @model_validator(mode="after")
    def _address_when_delivery(self) -> "SingleMealOrderCreateIn":
        if not self.store_pickup and self.member_address_id is None:
            raise ValueError("配送到家须选择配送地址")
        return self

    @field_validator("meal_period")
    @classmethod
    def _check_meal_period(cls, v: str) -> str:
        p = (v or "lunch").strip().lower()
        if p not in ("lunch", "dinner"):
            raise ValueError("meal_period 须为 lunch 或 dinner")
        return p


class SingleMealOrderOut(BaseModel):
    id: int
    out_trade_no: str = Field("", description="商户订单号")
    dish_id: int | None = None
    dish_title: str
    member_address_id: int | None = None
    store_pickup: bool = False
    quantity: int = 1
    delivery_date: date
    routing_area: str
    amount_yuan: str
    original_amount_yuan: str | None = Field(None, description="未用券时为 null")
    coupon_discount_yuan: str | None = Field(None, description="优惠券抵扣金额")
    member_coupon_id: int | None = Field(None, description="使用的用户券 id")
    pay_status: str
    pay_channel: str | None = None
    fulfillment_status: str = Field(
        ...,
        description="配送侧订单状态（英文枚举）：pending 待发货/待自提、sf_awaiting_pickup 顺丰待取货、accepted 配送中、delivered 已完成、sf_cancelled 顺丰取消、cancelled 已取消",
    )
    courier_id: str | None = None
    sf_same_city_push_id: int | None = Field(
        None, description="关联 sf_same_city_pushes.id（创单成功后写入）"
    )
    sf_order_id: str | None = Field(None, description="顺丰运单号（与推单表同步冗余）")
    address_summary: str
    store_contact_phone: str | None = Field(
        None,
        description="商家联系电话（来自门店配置）；小程序「联系商家」拨打",
    )
    created_at: datetime | None = Field(None, description="下单时间（北京时间，无时区列）")


class AdminSingleMealOrderListOut(SingleMealOrderOut):
    """管理端列表：在单次点餐订单上附带会员标识。"""

    member_id: int
    member_phone: str = ""
    member_name: str = Field(
        "",
        description="会员展示名：档案非占位时用 members.name，否则回退订单地址收件人",
    )
    recipient_contact_name: str = Field(
        "",
        description="订单关联地址收件人（member_addresses.contact_name）",
    )
    address_remarks: str = Field(
        "",
        description="订单关联配送地址备注（member_addresses.remarks）",
    )


class AdminSingleMealDeliveryAddressIn(BaseModel):
    """管理端手动建单：当场登记送餐地址（写入 meal 用途）。"""

    contact_name: str | None = Field(None, max_length=100, description="收件人；空则用会员姓名")
    contact_phone: str | None = Field(None, max_length=20, description="收货电话；空则用会员手机号")
    lng: float = Field(..., ge=-180, le=180, description="GCJ-02 经度（高德）")
    lat: float = Field(..., ge=-90, le=90, description="GCJ-02 纬度（高德）")
    map_location_text: str = Field(..., min_length=1, max_length=500)
    door_detail: str | None = Field(None, max_length=500)
    remarks: str | None = Field(None, max_length=500)


class AdminSingleMealOrderCreateIn(BaseModel):
    """管理端：为单次体验用户手动创建零售订单（默认已支付、占当日库存）。"""

    phone: str = Field(..., min_length=5, max_length=20, description="会员手机号")
    name: str | None = Field(
        None,
        max_length=100,
        description="会员不存在时须填写姓名以创建新会员",
    )
    delivery_date: date = Field(..., description="供餐日（与当前零售订单列表日期一致）")
    meal_period: str = Field("lunch", description="lunch=午餐；dinner=晚餐")
    dish_id: int | None = Field(
        None,
        ge=1,
        description="餐品 id；空则按供餐日+餐段自动取当日排期",
    )
    quantity: int = Field(1, ge=1, le=50, description="份数，默认 1，占用等量当日库存")
    store_pickup: bool = Field(False, description="门店自提")
    member_address_id: int | None = Field(
        None,
        ge=1,
        description="配送到家：选用已有送餐地址；与 delivery_address 二选一",
    )
    delivery_address: AdminSingleMealDeliveryAddressIn | None = Field(
        None,
        description="配送到家：当场登记送餐地址；与 member_address_id 二选一",
    )
    pay_channel: Literal["微信", "线下", "抖音"] = Field("线下", description="支付渠道")
    pay_status: Literal["已支付", "未支付"] = Field("已支付", description="支付状态")
    amount_yuan: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        description="实收金额；空则按单点价与配送方式自动计算",
    )

    @model_validator(mode="after")
    def _address_when_delivery(self) -> "AdminSingleMealOrderCreateIn":
        if self.store_pickup:
            return self
        if self.member_address_id is None and self.delivery_address is None:
            raise ValueError("配送到家须选择已有地址或登记新的收货地址")
        return self

    @field_validator("meal_period")
    @classmethod
    def _check_meal_period(cls, v: str) -> str:
        p = (v or "lunch").strip().lower()
        if p not in ("lunch", "dinner"):
            raise ValueError("meal_period 须为 lunch 或 dinner")
        return p
