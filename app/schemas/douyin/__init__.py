"""抖音团购：请求/响应 Schema。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import DouyinGrantType


class DouyinProductMappingCreateIn(BaseModel):
    """创建抖音商品映射。"""

    display_name: str = Field(..., min_length=1, max_length=128)
    douyin_product_id: str | None = Field(None, max_length=64)
    douyin_sku_id: str | None = Field(None, max_length=64)
    douyin_product_out_id: str | None = Field(None, max_length=64)
    grant_type: DouyinGrantType
    target_id: int | None = Field(None, ge=1)
    is_active: bool = True

    @model_validator(mode="after")
    def _validate_keys_and_target(self) -> "DouyinProductMappingCreateIn":
        keys = [
            (self.douyin_product_id or "").strip(),
            (self.douyin_sku_id or "").strip(),
            (self.douyin_product_out_id or "").strip(),
        ]
        if not any(keys):
            raise ValueError("至少填写一个抖音商品标识（product_id / sku_id / product_out_id）")
        gt = self.grant_type
        if gt in (
            DouyinGrantType.MEMBERSHIP_TEMPLATE,
            DouyinGrantType.COUPON_TEMPLATE,
            DouyinGrantType.RETAIL_PRODUCT,
        ):
            if self.target_id is None:
                raise ValueError("卡包、优惠券或商城商品映射须指定 target_id")
        elif self.target_id is not None:
            raise ValueError("周卡/月卡映射无需 target_id")
        return self


class DouyinProductMappingPatchIn(BaseModel):
    """编辑抖音商品映射。"""

    display_name: str | None = Field(None, min_length=1, max_length=128)
    douyin_product_id: str | None = Field(None, max_length=64)
    douyin_sku_id: str | None = Field(None, max_length=64)
    douyin_product_out_id: str | None = Field(None, max_length=64)
    grant_type: DouyinGrantType | None = None
    target_id: int | None = Field(None, ge=1)
    is_active: bool | None = None


class DouyinProductMappingOut(BaseModel):
    id: int
    display_name: str
    douyin_product_id: str | None = None
    douyin_sku_id: str | None = None
    douyin_product_out_id: str | None = None
    grant_type: str
    target_id: int | None = None
    is_active: bool
    created_by: str
    created_at: str | None = None
    updated_at: str | None = None


class DouyinRedemptionOut(BaseModel):
    """管理端核销记录。"""

    id: int
    member_id: int
    member_phone: str | None = None
    member_name: str | None = None
    code_masked: str | None = None
    douyin_order_id: str | None = None
    certificate_id: str
    douyin_product_id: str | None = None
    douyin_sku_id: str | None = None
    douyin_product_title: str | None = None
    mapping_display_name: str | None = None
    grant_type: str | None = None
    grant_target_id: int | None = None
    grant_result_kind: str | None = None
    grant_result_id: int | None = None
    status: str
    error_msg: str | None = None
    amount_yuan: str | None = None
    created_at: str | None = None


class DouyinCertificateRedeemIn(BaseModel):
    """小程序：粘贴券码兑换。"""

    code: str = Field(..., min_length=4, max_length=128, description="抖音订单券码明文")
    delivery_start_date: date | None = Field(
        None,
        description="保留字段；小程序验券不传，起送日在购卡/用券或「我的」完善配送时设置",
    )


class DouyinCertificateRedeemOut(BaseModel):
    """小程序：兑换结果。"""

    grant_type: str
    grant_label: str
    grant_result_kind: str | None = None
    grant_result_id: int | None = None
    message: str


class UserMemberCouponWalletOut(BaseModel):
    """小程序「我的优惠券」列表项。"""

    id: int
    template_name: str | None = None
    discount_yuan: str
    min_order_yuan: str
    biz_type: str
    scope_level: str
    status: str
    usage_instructions: str | None = None
    expires_at: str | None = None
    used_at: str | None = None
    issued_at: str | None = None
