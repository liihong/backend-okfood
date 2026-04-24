from datetime import date

from pydantic import BaseModel, ConfigDict, Field

class CourierLoginIn(BaseModel):
    courier_id: str = Field(..., min_length=1, max_length=50)
    pin: str = Field(..., min_length=4, max_length=32)


class CourierPhoneLoginIn(BaseModel):
    """配送员小程序：与后台登记的 mobile 一致即可登录（无需 PIN）。"""

    phone: str = Field(..., min_length=1, max_length=32)


class ConfirmDeliveryIn(BaseModel):
    """确认送达：默认可不传 date，表示「上海业务日」当天。"""

    model_config = ConfigDict(populate_by_name=True)

    member_id: int = Field(..., ge=1, description="会员主键 members.id")
    delivery_date: date | None = Field(None, alias="date")


class ConfirmSingleOrderIn(BaseModel):
    order_id: int = Field(..., ge=1, description="single_meal_orders.id")


class CourierTaskMemberOut(BaseModel):
    member_id: int
    phone: str
    name: str
    address: str
    lng: float | None
    lat: float | None
    area: str
    remarks: str | None
    daily_meal_units: int = Field(
        1,
        ge=1,
        description="每配送日份数（订阅）；单次点餐为当单份数",
    )
    sort_distance_m: float | None = None
    is_delivered: bool = Field(False, description="该业务日是否已确认送达")
    task_kind: str = Field("subscription", description="subscription 订阅配送 | single 单次点餐")
    single_order_id: int | None = None
    dish_title: str | None = Field(None, description="单次点餐餐品名")


class CourierSelfOut(BaseModel):
    """配送员小程序「我的」：基础信息与待结算配送费。"""

    courier_id: str
    name: str = ""
    phone_masked: str = ""
    fee_pending: str = "0.00"
    fee_settled: str = "0.00"
    assigned_areas: list[str] = Field(default_factory=list)
