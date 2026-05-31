"""小程序营销：优惠券相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import CouponBizType, CouponScopeLevel, CouponType, CouponValidityMode


class CouponTemplateCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    coupon_type: CouponType = Field(CouponType.CASH, description="MVP 仅 cash")
    discount_yuan: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    min_order_yuan: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    biz_type: CouponBizType
    scope_level: CouponScopeLevel = Field(CouponScopeLevel.ALL)
    scope_target_id: int | None = Field(None, ge=1)
    validity_mode: CouponValidityMode
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    valid_days_after_grant: int | None = Field(None, ge=1, le=3650)
    usage_instructions: str | None = Field(None, max_length=2000)
    sort_order: int = Field(0, ge=0, le=99999)
    is_active: bool = True
    max_grants: int | None = Field(None, ge=1, le=9999999)

    @model_validator(mode="after")
    def _validate_scope_and_validity(self) -> "CouponTemplateCreateIn":
        if self.coupon_type != CouponType.CASH:
            raise ValueError("当前仅支持代金券")
        if self.biz_type == CouponBizType.ALL:
            if self.scope_level != CouponScopeLevel.ALL or self.scope_target_id is not None:
                raise ValueError("全部小程序通用券无需细粒度范围")
        elif self.biz_type == CouponBizType.MEMBER_CARD:
            if self.scope_level == CouponScopeLevel.MEMBERSHIP_TEMPLATE and self.scope_target_id is None:
                raise ValueError("指定卡包须选择模板")
            if self.scope_level in (CouponScopeLevel.ALL, CouponScopeLevel.WEEK_MONTH):
                if self.scope_target_id is not None:
                    raise ValueError("该范围无需指定目标 id")
        elif self.biz_type == CouponBizType.SINGLE_MEAL:
            if self.scope_level == CouponScopeLevel.MENU_DISH and self.scope_target_id is None:
                raise ValueError("指定菜品须选择 dish_id")
            if self.scope_level == CouponScopeLevel.ALL and self.scope_target_id is not None:
                raise ValueError("全部单次零售无需指定菜品")
        elif self.biz_type == CouponBizType.STORE_RETAIL:
            if self.scope_level == CouponScopeLevel.RETAIL_PRODUCT and self.scope_target_id is None:
                raise ValueError("指定商品须选择 product_id")
            if self.scope_level == CouponScopeLevel.RETAIL_CATEGORY and self.scope_target_id is None:
                raise ValueError("指定类目须选择 category_id")
            if self.scope_level == CouponScopeLevel.ALL and self.scope_target_id is not None:
                raise ValueError("全部商城零售无需指定目标")
        if self.validity_mode == CouponValidityMode.FIXED_RANGE:
            if self.valid_from is None or self.valid_until is None:
                raise ValueError("固定有效期须填写起止时间")
            if self.valid_until <= self.valid_from:
                raise ValueError("结束时间须晚于开始时间")
        elif self.validity_mode == CouponValidityMode.DAYS_AFTER_GRANT:
            if self.valid_days_after_grant is None:
                raise ValueError("发放后有效天数不能为空")
        return self


class CouponTemplatePatchIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    discount_yuan: Decimal | None = Field(None, gt=0, max_digits=12, decimal_places=2)
    min_order_yuan: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    biz_type: CouponBizType | None = None
    scope_level: CouponScopeLevel | None = None
    scope_target_id: int | None = Field(None, ge=1)
    validity_mode: CouponValidityMode | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    valid_days_after_grant: int | None = Field(None, ge=1, le=3650)
    usage_instructions: str | None = Field(None, max_length=2000)
    sort_order: int | None = Field(None, ge=0, le=99999)
    is_active: bool | None = None
    max_grants: int | None = Field(None, ge=1, le=9999999)


class CouponTemplateActiveIn(BaseModel):
    is_active: bool


class CouponTemplateOut(BaseModel):
    id: int
    name: str
    coupon_type: str
    discount_yuan: str
    min_order_yuan: str
    biz_type: str
    scope_level: str
    scope_target_id: int | None = None
    validity_mode: str
    valid_from: str | None = None
    valid_until: str | None = None
    valid_days_after_grant: int | None = None
    usage_instructions: str | None = None
    sort_order: int
    is_active: bool
    max_grants: int | None = None
    grants_issued: int
    created_by: str
    created_at: str | None = None
    updated_at: str | None = None


class MemberCouponGrantIn(BaseModel):
    template_id: int = Field(..., ge=1)
    member_phone: str = Field(..., min_length=1, max_length=20, description="会员手机号")
    remark: str | None = Field(None, max_length=500)


class MemberCouponBatchGrantIn(BaseModel):
    template_id: int = Field(..., ge=1)
    member_phones: list[str] = Field(..., min_length=1, max_length=200, description="会员手机号列表")
    remark: str | None = Field(None, max_length=500)


class MemberCouponBatchGrantFailedItem(BaseModel):
    member_phone: str
    reason: str


class MemberCouponBatchGrantOut(BaseModel):
    success_count: int
    failed: list[MemberCouponBatchGrantFailedItem]
    items: list["MemberCouponOut"]


class MemberCouponOut(BaseModel):
    id: int
    template_id: int
    template_name: str | None = None
    member_id: int
    member_phone: str | None = None
    member_name: str | None = None
    discount_yuan: str
    min_order_yuan: str
    biz_type: str
    scope_level: str
    scope_target_id: int | None = None
    status: str
    expires_at: str | None = None
    locked_order_biz: str | None = None
    locked_order_id: int | None = None
    issued_by: str
    issued_at: str | None = None
    used_at: str | None = None
    revoked_at: str | None = None
    remark: str | None = None


class UserMemberCouponAvailableOut(BaseModel):
    """小程序结算页可用券列表项。"""

    id: int
    template_name: str | None = None
    discount_yuan: str
    min_order_yuan: str
    biz_type: str
    scope_level: str
    usage_instructions: str | None = None
    expires_at: str | None = None
