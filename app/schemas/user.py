from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

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
    tomorrow_leave_target_date: date | None = Field(
        None, description="仅明日请假：不配送目标业务日（上海）；有值时与配送/统计命中该日"
    )
    leave_range: dict[str, date | None] | None
    leave_deadline_time: str = Field(
        "21:00:00",
        description="门店请假截止时刻（HH:MM:SS）；自该时刻起至次日 09:00 小程序禁止自助请假",
    )
    leave_prep_locked: bool = Field(
        False,
        description="备餐锁窗内为 true：当日 leave_deadline_time 起至次日 09:00 禁止小程序自助请假",
    )
    pause_delivery_prep_locked: bool = Field(
        False,
        description="备餐锁窗内且已在履约日配送大表时为 true：禁止小程序暂停配送；已暂停会员为 false",
    )
    sf_self_service_locked: bool = Field(
        False,
        description="当日该会员已进配送大表且顺丰推单配送未完成时为 true；未进大表者为 false，可正常自助操作",
    )
    paid_card_awaiting_setup: bool = Field(
        False,
        description="小程序自助购卡微信已缴、尚未入账（balance 仍为 0）；须引导完善配送/自提信息",
    )
    created_at: str

    model_config = {"from_attributes": True}


class DeliveryDeductionOut(BaseModel):
    """会员消费记录：套餐送达扣次或单次购买（会员卡）扣次。"""

    delivery_date: date = Field(..., description="配送/供餐业务日（上海）")
    meal_units: int = Field(1, ge=1, description="本条扣减份数")
    deduction_kind: str = Field(
        default="subscription",
        description="subscription=套餐确认送达扣次；single_meal=单次购买会员卡扣次；meal_compensation=补餐赔付",
    )


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
    daily_meal_units: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="每配送日需送达份数；小程序自助修改范围 1～20，确认送达时按此倍数扣次",
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
    """小程序自助开卡/续卡：创建未缴工单，后续调 `.../pay/wechat-jsapi`。
    - 经典周/月卡：传 card_kind + delivery_start_date
    - 自律卡包（后台模版）：传 membership_template_id；起送日可延后至资料完善时写入
    """

    card_kind: CardOrderKind | None = None
    delivery_start_date: date | None = None
    membership_template_id: int | None = Field(None, ge=1)
    member_coupon_id: int | None = Field(None, ge=1, description="可选：使用的用户优惠券 id")

    @model_validator(mode="after")
    def _validate_mode(self):
        if self.membership_template_id is not None:
            if self.card_kind is not None:
                raise ValueError("请勿同时提交 membership_template_id 与 card_kind")
            return self
        if self.card_kind is None or self.delivery_start_date is None:
            raise ValueError("请选择卡型并填写起送日期，或使用 membership_template_id 购买卡包")
        return self


class UserMemberCardOrderApplyCouponIn(BaseModel):
    """未支付购卡单：绑定或更换优惠券。"""

    member_coupon_id: int | None = Field(None, ge=1, description="用户券 id；不传或 null 表示移除已选券")


class UserMemberCardOrderOut(BaseModel):
    id: int
    card_kind: str
    amount_yuan: str | None = None
    original_amount_yuan: str | None = Field(None, description="购卡标价原价")
    coupon_discount_yuan: str | None = Field(None, description="优惠券抵扣")
    member_coupon_id: int | None = Field(None, description="使用的用户券 id")
    pay_status: str
    delivery_start_date: str | None = None
    out_trade_no: str | None = None
    created_at: str | None = Field(default=None, description="下单时间（ISO8601，北京时间）")
    remark: str | None = Field(default=None, description="后台/卡包备注摘要")


class MemberCardPricesOut(BaseModel):
    """小程序展示用：当前周卡/月卡标价（与自助开卡下单金额一致，来源于门店或 app_settings）。"""

    week_price_yuan: str
    month_price_yuan: str
    week_list_price_yuan: str | None = Field(None, description="周卡划线价；高于售价时表示活动折扣")
    month_list_price_yuan: str | None = Field(None, description="月卡划线价；高于售价时表示活动折扣")
    promotion_active: bool = Field(
        False,
        description="任一侧划线价高于售价时为 true，启用「活动价」整体样式",
    )


class MembershipCardTemplateMemberOut(BaseModel):
    """后台会员卡模版：会员端展示（不参与下单计价；自助支付仍以门店周/月卡价为准）。"""

    id: int
    kind_label: str
    name: str
    meals_grant: int = Field(..., ge=1)
    list_price_yuan: str | None = Field(None, description="原价（划线价）")
    sale_price_yuan: str | None = Field(None, description="优惠价")
    card_style_image_url: str | None = None
    validity_days: int | None = Field(None, description="有效天数（展示）")
    intro_short: str | None = Field(None, description="商品简介")
    purchase_notice: str | None = Field(None, description="购买须知")
    sort_order: int = 0


class RenewRemindSubscribeGrantOut(BaseModel):
    wx_renew_remind_quota: int = Field(..., ge=0, description="续费提醒订阅消息剩余可发送次数")
