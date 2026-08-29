"""礼品券管理端入参/出参。与营销代金券 schema 分离，避免字段混用。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

GiftCouponStatus = Literal["draft", "active", "closed"]
GiftCouponEntitlementStatus = Literal["granted", "redeemed", "revoked"]
GiftCouponPlanKind = Literal["month", "quarter"]
GiftCouponGrantSource = Literal["rule", "manual"]
GiftCouponMatchMode = Literal["any_in_range"]


class GiftCouponCampaignCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="内部名称")
    sheet_label: str = Field(..., min_length=1, max_length=64, description="厨房标签礼品名")
    plan_kinds: list[GiftCouponPlanKind] = Field(..., min_length=1, description="月卡/季卡，可多选")
    credited_from: date = Field(..., description="入账日起（上海）")
    credited_to: date = Field(..., description="入账日止（上海）")
    exclude_membership_refunded: bool = Field(True, description="排除档案已退款")

    @field_validator("name", "sheet_label")
    @classmethod
    def _strip_text(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("不能为空")
        return s

    @field_validator("plan_kinds")
    @classmethod
    def _uniq_kinds(cls, v: list[GiftCouponPlanKind]) -> list[GiftCouponPlanKind]:
        seen: list[GiftCouponPlanKind] = []
        for k in v:
            if k not in seen:
                seen.append(k)
        if not seen:
            raise ValueError("请至少选择月卡或季卡")
        return seen

    @model_validator(mode="after")
    def _date_range(self) -> GiftCouponCampaignCreateIn:
        if self.credited_to < self.credited_from:
            raise ValueError("入账日结束不能早于开始")
        return self


class GiftCouponCampaignPatchIn(BaseModel):
    """仅草稿可改规则。"""

    name: str | None = Field(None, min_length=1, max_length=128)
    sheet_label: str | None = Field(None, min_length=1, max_length=64)
    plan_kinds: list[GiftCouponPlanKind] | None = Field(None, min_length=1)
    credited_from: date | None = None
    credited_to: date | None = None
    exclude_membership_refunded: bool | None = None

    @field_validator("name", "sheet_label")
    @classmethod
    def _strip_opt(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("不能为空")
        return s


class GiftCouponAudiencePreviewIn(BaseModel):
    """未保存活动时按表单规则预览圈人。"""

    plan_kinds: list[GiftCouponPlanKind] = Field(..., min_length=1)
    credited_from: date
    credited_to: date
    exclude_membership_refunded: bool = True

    @model_validator(mode="after")
    def _date_range(self) -> GiftCouponAudiencePreviewIn:
        if self.credited_to < self.credited_from:
            raise ValueError("入账日结束不能早于开始")
        return self


class GiftCouponAudienceMemberOut(BaseModel):
    member_id: int
    name: str
    phone: str
    card_kind_label: str = Field(..., description="入围工单的种类展示（模版种类或经典卡型）")
    credited_on: str = Field(..., description="入账日 YYYY-MM-DD")


class GiftCouponAudiencePreviewOut(BaseModel):
    total: int
    items: list[GiftCouponAudienceMemberOut]


class GiftCouponCampaignOut(BaseModel):
    id: int
    name: str
    sheet_label: str
    status: GiftCouponStatus
    plan_kinds: list[GiftCouponPlanKind]
    credited_from: str
    credited_to: str
    exclude_membership_refunded: bool
    match_mode: GiftCouponMatchMode
    created_by: str
    granted_at: str | None = None
    closed_at: str | None = None
    created_at: str
    granted_count: int = 0
    redeemed_count: int = 0
    revoked_count: int = 0


class GiftCouponEntitlementOut(BaseModel):
    id: int
    campaign_id: int
    campaign_name: str
    sheet_label: str
    member_id: int
    member_name: str
    member_phone: str
    status: GiftCouponEntitlementStatus
    grant_source: GiftCouponGrantSource
    granted_at: str
    granted_by: str
    redeemed_at: str | None = None
    redeemed_delivery_date: str | None = None
    redeemed_by: str | None = None
    revoked_at: str | None = None
    revoked_by: str | None = None


class GiftCouponManualGrantIn(BaseModel):
    campaign_id: int = Field(..., ge=1)
    member_phones: list[str] = Field(..., min_length=1, description="手机号列表")


class GiftCouponManualGrantFailedItem(BaseModel):
    member_phone: str
    reason: str


class GiftCouponManualGrantOut(BaseModel):
    success_count: int
    failed: list[GiftCouponManualGrantFailedItem]
    items: list[GiftCouponEntitlementOut]


class GiftCouponTodayRowOut(BaseModel):
    """当日大表 ∩ 未核销资格，供勾选打印。不含会员档案备注。"""

    entitlement_id: int
    campaign_id: int
    campaign_name: str
    sheet_label: str
    member_id: int
    name: str
    phone: str
    area: str = ""
    address_line: str = ""
    store_pickup: bool = False


class GiftCouponTodayListOut(BaseModel):
    delivery_date: str
    sheet_view: str
    items: list[GiftCouponTodayRowOut]


class GiftCouponRedeemIn(BaseModel):
    delivery_date: date
    sheet_view: str = Field("lunch", description="与当前大表视图一致")
    entitlement_ids: list[int] = Field(..., min_length=1, description="勾选要配送的资格 id")


class GiftCouponRedeemOut(BaseModel):
    redeemed_count: int
    already_redeemed_count: int
    skipped_not_on_sheet: int
    items: list[GiftCouponTodayRowOut]
