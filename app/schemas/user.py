from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import CardOrderKind, LeaveType, PlanType


class Location(BaseModel):
    lng: float
    lat: float


class MemberOut(BaseModel):
    id: int = Field(..., description="会员主键，与 JWT sub 一致")
    phone: str
    name: str
    wechat_name: str | None = None
    address: str
    avatar_url: str | None
    location: Location | None
    area: str = Field(..., description="默认地址所属配送片区展示名（由 delivery_regions 解析）")
    remarks: str | None
    balance: int
    daily_meal_units: int = Field(1, ge=1, description="每配送日份数（订阅）；确认送达时按此倍数扣次")
    meal_quota_total: int = Field(
        0,
        ge=0,
        description="周卡/月卡累计总次数（与 balance 组成剩余/总）；次卡或未启用可为 0",
    )
    plan_type: PlanType | None
    delivery_start_date: date | None = Field(None, description="起送业务日（上海）")
    delivery_deferred: bool = Field(False, description="用户选择暂不配送，无起送日且未开卡")
    store_pickup: bool = Field(False, description="门店自提：不参与配送线路，仍参与起送日与备餐统计")
    is_active: bool
    is_leaved_tomorrow: bool
    leave_range: dict[str, date | None] | None
    created_at: str

    model_config = {"from_attributes": True}


class RegisterIn(BaseModel):
    phone: str = Field(..., min_length=5, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    address: str = Field(..., min_length=1, max_length=500)
    remarks: str | None = Field(None, max_length=500)
    avatar_url: str | None = Field(None, max_length=512)


class ProfilePatchIn(BaseModel):
    avatar_url: str | None = Field(default=None, max_length=512)
    wechat_name: str | None = Field(default=None, max_length=100)
    name: str | None = Field(
        default=None,
        max_length=100,
        description="仅当后台档案仍为占位姓名时由服务端接受写入",
    )
    plan_type: PlanType | None = Field(
        default=None,
        description="开卡意向：周卡 / 月卡 / 次卡",
    )
    delivery_start_date: date | None = Field(
        default=None,
        description="会员自选起送业务日（上海）；空表示不限制",
    )
    delivery_deferred: bool | None = Field(
        default=None,
        description="为 true 时表示暂不配送：清空起送日并 is_active=false；为 false 时取消该标记",
    )
    store_pickup: bool | None = Field(
        default=None,
        description="为 true 时门店自提（与配送互斥）；为 false 时恢复配送到家；暂不配送时会由服务端清零",
    )
    card_pay_mode: Literal["offline_paid"] | None = Field(
        default=None,
        description="仅剩余次数为 0 需购卡时：offline_paid 表示用户自报已线下/其他方式缴费；保持未开卡并生成待核开卡工单（不自动入账）",
    )


class ActivateIn(BaseModel):
    """激活计划：身份以会员 JWT（members.id）为准，Body 可为空对象。"""

    model_config = {"extra": "ignore"}


class LeaveIn(BaseModel):
    """请假：身份以会员 JWT 为准；`type` 含 clear_tomorrow（仅去掉明天请假）。"""
    type: LeaveType
    start: date | None = None
    end: date | None = None


class WxMiniLoginIn(BaseModel):
    """小程序 `wx.login` 的 js_code + `getPhoneNumber` 返回的 code。"""

    js_code: str = Field(..., min_length=8, max_length=256)
    phone_code: str = Field(..., min_length=8, max_length=512)


class WxMiniJsCodeIn(BaseModel):
    """仅 `wx.login` 的 js_code：已登录会员绑定/刷新小程序 openid（用于支付等）。"""

    js_code: str = Field(..., min_length=8, max_length=256)


class UserMemberCardOrderCreateIn(BaseModel):
    """小程序自助开卡/续卡：创建未缴工单，后续调 `.../pay/wechat-jsapi`。"""

    card_kind: CardOrderKind
    delivery_start_date: date


class UserMemberCardOrderOut(BaseModel):
    id: int
    card_kind: str
    amount_yuan: str | None = None
    pay_status: str
    delivery_start_date: str | None = None
    out_trade_no: str | None = None


class MemberCardPricesOut(BaseModel):
    """小程序展示用：当前周卡/月卡标价（与自助开卡下单金额一致，来源于 app_settings）。"""

    week_price_yuan: str
    month_price_yuan: str
