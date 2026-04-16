from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import (
    CardOrderKind,
    CardOrderPayStatus,
    CardPayChannel,
    PlanType,
)


class AdminLoginIn(BaseModel):
    username: str
    password: str


class RechargeIn(BaseModel):
    phone: str
    amount: int = Field(..., description="正数为增加次数，负数为扣减")
    plan_type: PlanType | None = None


class DishUpsertIn(BaseModel):
    """新建时省略 id；更新时带 id。"""

    id: int | None = Field(None, ge=1)
    name: str = Field(..., max_length=200)
    description: str | None = Field(None, max_length=1000)
    image_url: str | None = Field(None, max_length=2_000_000)
    is_enabled: bool = True
    category_id: int | None = Field(default=None, description="商品分类主键，可空")


class DishAdminOut(BaseModel):
    id: int
    name: str
    description: str | None
    image_url: str | None
    is_enabled: bool
    category_id: int | None
    created_at: str


class FileUploadOut(BaseModel):
    """本地上传成功后的地址，可直接写入菜品的 image_url。"""

    url: str = Field(..., description="图片绝对或相对 URL（由 BASE_URL 与路径拼接）")


class CategoryAdminOut(BaseModel):
    id: int
    code: str
    name: str
    sort_order: int
    is_active: bool


class CategoryCreateIn(BaseModel):
    code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=64)
    sort_order: int = 0


class WeeklySlotAssignIn(BaseModel):
    """维护某周第几天（slot 1–7）对应的菜品；dish_id 为空则清空该槽。"""

    week_start: date = Field(..., description="该周任意一天，服务端归一为周一")
    slot: int = Field(..., ge=1, le=7, description="1=周一 … 7=周日")
    dish_id: int | None = Field(None, ge=1)


class MenuScheduleAssignIn(BaseModel):
    date: date
    dish_id: int = Field(..., ge=1)


class SettingsIn(BaseModel):
    leave_deadline_time: time


class MemberAdminOut(BaseModel):
    id: int = Field(..., description="会员主键 members.id")
    phone: str
    name: str
    wechat_name: str | None = None
    delivery_start_date: date | None = Field(
        None,
        description="起送业务日（上海）：非空则仅当配送日>=该日才进入配送大表；开卡工单同步时写入",
    )
    address: str
    detail_address: str = Field(
        "",
        description="默认配送地址详细行（不含片区前缀）；编辑表单应使用本字段，勿用 address 展示列",
    )
    avatar_url: str | None
    area: str
    area_manual: bool = Field(False, description="默认地址片区是否为后台手工指定")
    remarks: str | None = None
    balance: int
    plan_type: str | None
    is_active: bool
    is_leaved_tomorrow: bool = Field(False, description="已勾选仅明天请假（不影响今日配送）")
    leave_range_start: date | None = None
    leave_range_end: date | None = None
    is_on_leave_today: bool = Field(False, description="区间请假是否覆盖上海当前业务日")
    created_at: str


class AdminAddressIn(BaseModel):
    phone: str
    address: str = Field(..., min_length=1, max_length=500)


class AdminMemberPatchIn(BaseModel):
    """管理端修改会员档案：至少填一项；手机号不可改。"""

    phone: str = Field(..., min_length=5, max_length=20)
    name: str | None = Field(None, max_length=100)
    remarks: str | None = Field(None, max_length=500)
    address: str | None = Field(None, max_length=500, description="默认配送地址详细行，提交则重算坐标；片区是否重算见 area_manual / use_auto_area")
    delivery_area: str | None = Field(
        None,
        max_length=64,
        description="手工指定默认地址的配送片区名；与 use_auto_area 互斥",
    )
    use_auto_area: bool = Field(
        False,
        description="按当前坐标重新自动划区并取消手工锁定；与 delivery_area 互斥",
    )


class DashboardMealSummaryOut(BaseModel):
    """营业概览：与配送清单同一规则（激活且有余额；请假含区间与「仅明天请假」）。"""

    today_leave_members: int = Field(..., description="今日请假会员数")
    today_meals_to_prepare: int = Field(..., description="今日需准备餐品份数")
    tomorrow_leave_members: int = Field(..., description="明日请假会员数")
    tomorrow_meals_to_prepare: int = Field(..., description="明日需准备餐品份数")


class DeliverySheetMemberOut(BaseModel):
    phone: str
    name: str
    remarks: str | None = None
    area_issue: bool = Field(False, description="会员主档或默认地址片区为空、未分配或与启用区域表不一致")


class DeliverySheetStopOut(BaseModel):
    """同一收件地址聚合为一配送点；meal_count 为当日该址份数。"""

    meal_count: int = Field(..., ge=1)
    address_line: str = Field(..., description="收件地址单行展示")
    area: str = Field(..., description="该配送点展示用片区（来自默认地址或会员主档）")
    members: list[DeliverySheetMemberOut]
    remarks_combined: str | None = Field(None, description="多名会员备注去重合并")
    has_area_issue: bool = Field(
        False,
        description="本配送点存在区域未维护/未分配或与启用 delivery_regions 不匹配",
    )


class DeliverySheetGroupOut(BaseModel):
    area: str = Field(..., description="与默认配送地址 effective 片区一致，用于与配送员分组对齐")
    stops: list[DeliverySheetStopOut]
    stop_count: int = Field(..., ge=0)
    meal_total: int = Field(..., ge=0)
    has_area_issue: bool = Field(False, description="本片区分组存在区域待处理记录")


class DeliverySheetOut(BaseModel):
    delivery_date: str
    groups: list[DeliverySheetGroupOut]
    active_regions: list[str] = Field(
        default_factory=list,
        description="delivery_regions 中 is_active=1 的名称列表，与筛选下拉同源",
    )


class CardOrderCreateIn(BaseModel):
    phone: str = Field(..., min_length=5, max_length=20)
    delivery_start_date: date = Field(
        ...,
        description="起送业务日（上海）：此前不参与配送大表；同步入账时写入会员并激活计划",
    )
    card_kind: CardOrderKind
    pay_channel: CardPayChannel
    pay_status: CardOrderPayStatus = CardOrderPayStatus.UNPAID
    amount_yuan: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    remark: str | None = Field(None, max_length=500)
    sync_member: bool = Field(
        False,
        description="当缴费状态为已缴时，是否立即按周卡+6次/月卡+24次入账并更新会员 plan_type",
    )


class CardOrderPatchIn(BaseModel):
    delivery_start_date: date | None = None
    pay_status: CardOrderPayStatus | None = None
    pay_channel: CardPayChannel | None = None
    amount_yuan: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    remark: str | None = Field(None, max_length=500)
    sync_member: bool = Field(
        False,
        description="当工单为已缴且尚未入账时，是否同步会员次数（可与其它字段一并提交）",
    )


class CardOrderOut(BaseModel):
    id: int
    member_id: int
    member_phone: str
    member_name: str
    delivery_start_date: str | None = Field(None, description="起送业务日 ISO")
    card_kind: str
    pay_channel: str
    pay_status: str
    amount_yuan: str | None = Field(None, description="元，字符串保留两位小数")
    remark: str | None
    applied_to_member: bool
    created_by: str
    created_at: str
    updated_at: str
