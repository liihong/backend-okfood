from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import LeaveType, PlanType


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
    area: str
    area_manual: bool = Field(False, description="默认地址片区是否为后台手工指定（改地址时不自动重算）")
    remarks: str | None
    balance: int
    plan_type: PlanType | None
    delivery_start_date: date | None = Field(None, description="起送业务日（上海）")
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


class ActivateIn(BaseModel):
    """激活计划：身份以会员 JWT（members.id）为准，Body 可为空对象。"""

    model_config = {"extra": "ignore"}


class LeaveIn(BaseModel):
    """请假：身份以会员 JWT 为准；`type` 含 clear_tomorrow（仅去掉明天请假）。"""
    type: LeaveType
    start: date | None = None
    end: date | None = None


class SmsSendIn(BaseModel):
    phone: str


class SmsLoginIn(BaseModel):
    phone: str
    code: str


class WxMiniLoginIn(BaseModel):
    """小程序 `wx.login` 的 js_code + `getPhoneNumber` 返回的 code。"""

    js_code: str = Field(..., min_length=8, max_length=256)
    phone_code: str = Field(..., min_length=8, max_length=512)
