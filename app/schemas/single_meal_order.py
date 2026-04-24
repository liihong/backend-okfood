from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class SingleMealOrderCreateIn(BaseModel):
    dish_id: int = Field(..., ge=1)
    member_address_id: int | None = Field(
        default=None,
        ge=1,
        description="配送到家时必填：会员已保存的配送地址 id；门店自提勿传",
    )
    delivery_date: date = Field(..., description="与周菜单该道菜对应的供餐日")
    store_pickup: bool = Field(False, description="门店自提：无需地址，支付后不派骑手")
    quantity: int = Field(1, ge=1, le=50, description="份数，总价=单价×份数")

    @model_validator(mode="after")
    def _address_when_delivery(self) -> "SingleMealOrderCreateIn":
        if not self.store_pickup and self.member_address_id is None:
            raise ValueError("配送到家须选择配送地址")
        return self


class SingleMealOrderOut(BaseModel):
    id: int
    out_trade_no: str = Field("", description="商户订单号")
    dish_id: int
    dish_title: str
    member_address_id: int | None = None
    store_pickup: bool = False
    quantity: int = 1
    delivery_date: date
    routing_area: str
    amount_yuan: str
    pay_status: str
    pay_channel: str | None = None
    fulfillment_status: str
    courier_id: str | None = None
    address_summary: str
    created_at: datetime | None = Field(None, description="下单时间(UTC)")
