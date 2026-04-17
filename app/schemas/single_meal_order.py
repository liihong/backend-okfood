from datetime import date

from pydantic import BaseModel, Field


class SingleMealOrderCreateIn(BaseModel):
    dish_id: int = Field(..., ge=1)
    member_address_id: int = Field(..., ge=1, description="会员已保存的配送地址 id")
    delivery_date: date = Field(..., description="与周菜单该道菜对应的供餐日")


class SingleMealOrderOut(BaseModel):
    id: int
    dish_id: int
    dish_title: str
    member_address_id: int
    delivery_date: date
    routing_area: str
    amount_yuan: str
    pay_status: str
    pay_channel: str | None = None
    fulfillment_status: str
    courier_id: str | None = None
    address_summary: str
