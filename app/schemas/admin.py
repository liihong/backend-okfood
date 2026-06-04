from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from app.models.enums import (
    CardOpenMode,
    CardOrderKind,
    CardOrderPayStatus,
    CardPayChannel,
    LeaveType,
    PlanType,
)


class AdminLoginIn(BaseModel):
    username: str
    password: str


class RechargeIn(BaseModel):
    phone: str
    amount: int = Field(..., description="正数为增加次数，负数为扣减")
    plan_type: PlanType | None = None
    bump_meal_quota_total: bool = Field(
        False,
        description="正向入账时同步累加 meal_quota_total（自律卡包模版等标准周/月枚举无法覆盖的餐次）",
    )


DishSpiceLevelCode = Literal["none", "mild", "medium", "hot"]


class DishUpsertIn(BaseModel):
    """新建时省略 id；更新时带 id。"""

    id: int | None = Field(None, ge=1)
    name: str = Field(..., max_length=200)
    description: str | None = Field(None, max_length=1000)
    image_url: str | None = Field(None, max_length=2_000_000)
    is_enabled: bool = True
    category_id: int | None = Field(default=None, description="商品分类主键，可空")
    single_order_price_yuan: Decimal | None = Field(
        None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="单点售价(元)，可空表示未定价",
    )
    spice_level: DishSpiceLevelCode | None = Field(None, description="辣度：none 不辣 / mild 微微辣 / medium 微辣 / hot 较辣")
    internal_view_sop: str | None = Field(
        None,
        max_length=16000,
        description="内部查看操作说明，不对会员端返回",
    )


class DishAdminOut(BaseModel):
    id: int
    name: str
    description: str | None
    image_url: str | None
    is_enabled: bool
    category_id: int | None
    single_order_price_yuan: str | None = Field(None, description="单点售价(元)，字符串保留两位小数")
    spice_level: DishSpiceLevelCode | None = None
    internal_view_sop: str | None = None
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


class MenuDayTotalStockIn(BaseModel):
    """某日槽位在 menu_date 上的总份数；不传 total_stock 或传 null 表示未配置（单次卡不可售）。"""

    week_start: date = Field(..., description="该周任意一天，服务端归一为周一")
    slot: int = Field(..., ge=1, le=7, description="1=周一 … 7=周日")
    total_stock: int | None = Field(default=None, description="当日该菜总可供应份数；null=未配置(不可售)")


class MenuScheduleAssignIn(BaseModel):
    date: date
    dish_id: int = Field(..., ge=1)


class SettingsIn(BaseModel):
    leave_deadline_time: time


class StoreConfigOut(BaseModel):
    """门店基础信息：用于管理端展示与配送地图锚点。"""

    store_id: int = Field(1, ge=1, description="门店主键 stores.id")
    store_name: str | None = Field(None, max_length=128)
    store_logo_url: str | None = Field(None, max_length=512)
    store_lng: float | None = Field(None, description="GCJ-02 经度")
    store_lat: float | None = Field(None, description="GCJ-02 纬度")
    store_contact_phone: str | None = Field(
        None,
        max_length=20,
        description="商家联系电话；小程序订单详情「联系商家」直接拨打",
    )
    courier_delivery_base_yuan: Decimal = Field(
        ...,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="骑手配送费首份基础价（元）",
    )
    courier_delivery_extra_per_unit_yuan: Decimal = Field(
        ...,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="同地址每多一份加价（元）",
    )
    member_card_week_price_yuan: Decimal = Field(
        ...,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="小程序周卡微信支付标价（元）",
    )
    member_card_month_price_yuan: Decimal = Field(
        ...,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="小程序月卡微信支付标价（元）",
    )
    member_card_week_list_price_yuan: Decimal | None = Field(
        None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="周卡划线原价（元）；高于微信支付标价时小程序展示活动价样式",
    )
    member_card_month_list_price_yuan: Decimal | None = Field(
        None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="月卡划线原价（元）；高于微信支付标价时小程序展示活动价样式",
    )
    sf_nightly_auto_push_enabled: bool = Field(
        False,
        description="每日 08:50（上海）自动向顺丰推送当日业务日配送大表（订阅合并）订单；单次零售须手动推单",
    )
    sf_retail_push_shop_id: str | None = Field(
        None,
        max_length=64,
        description="单次点餐/零售单推顺丰：顺丰店铺编号，与租户对接中的 shop（大表推单）独立",
    )
    sf_retail_push_shop_type: int | None = Field(
        None,
        description="零售推顺丰 shop_type；空则与租户/全局一致",
    )
    uu_open_app_id: str | None = Field(None, max_length=64, description="UU 跑腿 AppId（预留）")
    uu_open_app_key_set: bool = Field(False, description="UU 跑腿 AppKey 是否已在库中填写（不回传密钥明文）")
    wechat_pay_ssl_cert_path: str | None = Field(
        None,
        max_length=512,
        description="本门店微信退款 apiclient_cert.pem 路径；空则回退租户对接或全局 .env",
    )
    wechat_pay_ssl_key_path: str | None = Field(
        None,
        max_length=512,
        description="本门店微信退款 apiclient_key.pem 路径；空则回退租户对接或全局 .env",
    )
    douyin_poi_id: str | None = Field(None, max_length=64, description="抖音来客核销门店 POI ID")
    douyin_account_id: str | None = Field(None, max_length=64, description="抖音核销商户根账户 ID（可选）")


class StoreConfigUpdateIn(BaseModel):
    """PATCH 语义：仅提交需要修改的字段；经纬度须成对出现或成对清空。"""

    store_name: str | None = Field(None, max_length=128)
    store_logo_url: str | None = Field(None, max_length=512)
    store_lng: float | None = Field(None, ge=-180, le=180)
    store_lat: float | None = Field(None, ge=-90, le=90)
    store_contact_phone: str | None = Field(
        None,
        max_length=20,
        description="商家联系电话；传空字符串可清空",
    )
    courier_delivery_base_yuan: Decimal | None = Field(
        None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    courier_delivery_extra_per_unit_yuan: Decimal | None = Field(
        None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    member_card_week_price_yuan: Decimal | None = Field(
        None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    member_card_month_price_yuan: Decimal | None = Field(
        None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    member_card_week_list_price_yuan: Decimal | None = Field(
        None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="留空或不传表示清除划线价",
    )
    member_card_month_list_price_yuan: Decimal | None = Field(
        None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="留空或不传表示清除划线价",
    )
    sf_nightly_auto_push_enabled: bool | None = Field(
        None,
        description="顺丰自动推单；不传表示不修改",
    )
    sf_retail_push_shop_id: str | None = Field(
        None,
        max_length=64,
        description="零售推顺丰 shop_id；传空字符串可清空",
    )
    sf_retail_push_shop_type: int | None = Field(
        None,
        description="零售推顺丰 shop_type；不传不修改",
    )
    uu_open_app_id: str | None = Field(None, max_length=64, description="UU 预留；传空字符串可清空")
    uu_open_app_key: str | None = Field(
        None,
        max_length=255,
        description="UU 预留 AppKey；不传不修改，传空字符串可清空",
    )
    wechat_pay_ssl_cert_path: str | None = Field(
        None,
        max_length=512,
        description="退款 cert 路径；传 null 或不传表示不修改，传空字符串可清空本门店覆盖",
    )
    wechat_pay_ssl_key_path: str | None = Field(
        None,
        max_length=512,
        description="退款 key 路径；传 null 或不传表示不修改，传空字符串可清空本门店覆盖",
    )
    douyin_poi_id: str | None = Field(None, max_length=64, description="抖音 POI；传空字符串可清空")
    douyin_account_id: str | None = Field(None, max_length=64, description="抖音 account_id；传空字符串可清空")

    @model_validator(mode="after")
    def _lng_lat_pair(self) -> Self:
        fs = self.model_fields_set
        has_lng = "store_lng" in fs
        has_lat = "store_lat" in fs
        if has_lng ^ has_lat:
            raise ValueError("更新门店坐标时请同时提交经度与纬度")
        if has_lng and has_lat and (self.store_lng is None) != (self.store_lat is None):
            raise ValueError("门店经纬度须同时填写或同时清空")
        return self


class SingleMealAssignCourierIn(BaseModel):
    """单次点餐：门店自配送指派（系统内配送员 courier_id）。"""

    courier_id: str = Field(..., min_length=1, max_length=50, description="couriers.courier_id 主键")


class SingleMealOrderIdsIn(BaseModel):
    """单次点餐：批量操作订单 id 列表。"""

    order_ids: list[int] = Field(..., min_length=1, max_length=100)


class SingleMealBatchAssignCourierIn(BaseModel):
    """单次点餐：批量门店自配送指派。"""

    order_ids: list[int] = Field(..., min_length=1, max_length=100)
    courier_id: str = Field(..., min_length=1, max_length=50, description="couriers.courier_id 主键")


class SingleMealPatchIn(BaseModel):
    """单次点餐：管理端修改配送方式与收货地址。"""

    store_pickup: bool = Field(..., description="true=门店自提；false=配送到家")
    member_address_id: int | None = Field(
        None,
        ge=1,
        description="配送到家时必填：会员已保存的配送地址 id；门店自提勿传",
    )

    @model_validator(mode="after")
    def _address_when_delivery(self) -> "SingleMealPatchIn":
        if not self.store_pickup and self.member_address_id is None:
            raise ValueError("配送到家须选择配送地址")
        return self


class SingleMealCancelIn(BaseModel):
    """单次点餐：管理端取消订单。"""

    cancel_reason: str | None = Field(None, max_length=200, description="取消原因（已推顺丰时传给顺丰）")
    cancel_sf: bool = Field(True, description="若已推顺丰且配送未完结，是否同步请求顺丰取消")


class SingleMealBatchCancelIn(SingleMealCancelIn):
    """单次点餐：批量取消订单。"""

    order_ids: list[int] = Field(..., min_length=1, max_length=100)


class SingleMealBatchOperationItemResult(BaseModel):
    order_id: int
    ok: bool
    message: str
    sf_order_id: str | None = None


class SingleMealBatchOperationOut(BaseModel):
    results: list[SingleMealBatchOperationItemResult] = Field(default_factory=list)


class MemberAdminOut(BaseModel):
    id: int = Field(..., description="会员主键 members.id")
    phone: str
    name: str
    wechat_name: str | None = None
    delivery_start_date: date | None = Field(
        None,
        description="起送业务日（上海）：非空则仅当配送日>=该日才进入配送大表；开卡工单同步时写入",
    )
    store_pickup: bool = Field(False, description="门店自提，不参与骑手任务与按地址配送分组")
    skip_subscription_saturday: bool = Field(
        False,
        description="固定周六不参与订阅履约（全局日历仍为履约日时，到家与自提名单均排除）",
    )
    address: str
    map_location_text: str = Field(
        "",
        description="默认地址：地图定位/收货主文案 segment；与小程序 member_addresses.map_location_text 一致",
    )
    door_detail: str = Field(
        "",
        description="默认地址：门牌 segment；与 member_addresses.door_detail 一致；完整地址请拼接二者",
    )
    avatar_url: str | None
    area: str = Field(..., description="默认地址配送片区展示名")
    delivery_region_id: int | None = Field(
        None,
        description="默认地址绑定的配送区域 id；未分配时为 null",
    )
    remarks: str | None = None
    balance: int
    daily_meal_units: int = Field(1, ge=1, description="每配送日份数；与配送扣次、备餐统计一致")
    meal_quota_total: int = Field(
        0,
        ge=0,
        description="周卡/月卡累计总次数（展示分母）；0 表示未启用或与次卡同源仅用 balance",
    )
    plan_type: str | None
    is_active: bool
    delivery_deferred: bool = Field(
        False,
        description="会员卡停用(暂不配送/先不开卡/暂停配送)；与 is_active/起送日 联动，同 members.delivery_deferred",
    )
    is_leaved_tomorrow: bool = Field(False, description="已勾选仅明天请假（不影响今日配送）")
    tomorrow_leave_target_date: date | None = Field(
        None,
        description="仅明日请假：不配送的目标业务日（上海）；与 is_leaved_tomorrow 同时有效",
    )
    leave_range_start: date | None = None
    leave_range_end: date | None = None
    is_on_leave_today: bool = Field(False, description="区间请假是否覆盖上海当前业务日")
    membership_refunded_at: str | None = Field(
        None,
        description="退卡退款确认时刻（ISO）；非空则档案状态为已退款",
    )
    created_at: str
    updated_at: str = Field("", description="用户操作时间（档案最近更新时间，ISO 上海墙钟；列表默认按此倒序）")


class MemberListStatsOut(BaseModel):
    """会员档案库顶栏统计：与列表 validity 筛选一致。"""

    total: int = Field(..., ge=0, description="周/月卡档案总户数")
    active: int = Field(..., ge=0, description="生效中：balance>0")
    expired: int = Field(..., ge=0, description="已过期：次数用尽且未退卡")
    refunded: int = Field(..., ge=0, description="已退款：membership_refunded_at 非空")
    refund_rate_percent: Decimal = Field(
        ...,
        ge=0,
        max_digits=6,
        decimal_places=2,
        description="退款率 = 已退款 / 总户数 × 100",
    )


class AdminAddressIn(BaseModel):
    phone: str
    address: str = Field(..., min_length=1, max_length=500)


class AdminMemberLeaveIn(BaseModel):
    """管理端手工请假：与小程序 `/api/user/leave` 类型一致；后台代操作不校验当日请假截止时间。"""

    phone: str = Field(..., min_length=5, max_length=20)
    type: LeaveType
    start: date | None = None
    end: date | None = None


class AdminMemberPatchIn(BaseModel):
    """管理端修改会员档案：至少填一项；手机号不可改。"""

    phone: str = Field(..., min_length=5, max_length=20)
    name: str | None = Field(None, max_length=100)
    remarks: str | None = Field(
        None, max_length=500, description="显式传 null 或空串表示清空；不传本字段则不改备注"
    )
    address: str | None = Field(None, max_length=500, description="默认配送地址详细行，提交则重算坐标与自动划区")
    use_auto_area: bool = Field(
        False,
        description="按当前详细地址与坐标重新自动划区；若无坐标则先尝试高德地理编码再划区；为 true 时不采用手动指定的 delivery_region_id",
    )
    delivery_region_id: int | None = Field(
        None,
        description="手动指定默认地址的配送片区 id；提交 null 表示清空片区。与 use_auto_area 同时为 true 时以自动划区为准",
    )
    daily_meal_units: int | None = Field(
        None,
        ge=1,
        le=50,
        validation_alias=AliasChoices("daily_meal_units", "dailyMealUnits"),
        description="每配送日需送达份数；不传则不修改（可与前端约定 snake_case 或 camelCase）",
    )
    plan_type: PlanType | None = Field(
        None,
        description="仅更新档案套餐标签（周卡/月卡/次卡），不改动余额；与开卡工单入账互补",
    )
    balance: int | None = Field(
        None,
        ge=0,
        le=999_999,
        description="会员剩余次数；提交则整单覆盖，差值写入 balance_logs",
    )
    delivery_start_date: date | None = Field(
        None,
        description="起送业务日（上海）：提交则更新；可清空为不参与排期；通常与 is_active/请假等一同生效",
    )
    store_pickup: bool | None = Field(
        None,
        description="门店自提；提交则更新；与配送到家互斥",
    )
    skip_subscription_saturday: bool | None = Field(
        None,
        description="固定周六不参与订阅履约；提交则更新",
    )
    delivery_deferred: bool | None = Field(
        None,
        description="会员卡停用(暂停配送/先不开卡)：与小程序「暂不配送」同字段；为 true 时 is_active=false 并清空起送日；提交则总是更新本项时传入 true/false",
    )

    @field_validator("daily_meal_units", mode="before")
    @classmethod
    def _coerce_daily_meal_units(cls, v: object) -> int | None:
        """兼容 JSON 数字串、空串；避免校验失败导致整单422。"""
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return None
            try:
                v = int(s, 10)
            except ValueError as e:
                raise ValueError("每配送日份数须为 1～50 的整数") from e
        if isinstance(v, bool):
            raise ValueError("每配送日份数格式无效")
        if isinstance(v, float):
            if abs(v - round(v)) > 1e-9:
                raise ValueError("每配送日份数须为整数")
            v = int(round(v))
        return v


class DashboardDayPrepMetricsOut(BaseModel):
    """单日备餐拆分：与配送大表根级汇总及到家停靠点计数同源，不含完整 groups。"""

    home_pending_meal_total: int = Field(0, ge=0, description="到家待送达份数")
    home_delivered_meal_total: int = Field(0, ge=0, description="到家已送达份数")
    pickup_meal_total: int = Field(0, ge=0, description="门店自提总份数")
    pickup_pending_meal_total: int = Field(0, ge=0, description="自提待履约份数")
    pickup_delivered_meal_total: int = Field(0, ge=0, description="自提已履约份数")
    home_stop_count: int = Field(0, ge=0, description="到家配送点数量（不含门店自提）")


class DashboardMealSummaryOut(BaseModel):
    """营业概览：备餐份数与智能配送大表一致；过去业务日可读快照（首读落库后不变）。"""

    shanghai_today: date = Field(..., description="服务端当前上海日历日（区分历史锚日）")
    business_anchor_date: date = Field(..., description="本响应中「今日/明日」所锚定的业务日(上海)，「明日」为其日历次日")
    today_leave_members: int = Field(..., description="今日请假会员数")
    today_meals_to_prepare: int = Field(..., description="今日需准备餐品份数（与大表分组合计一致）")
    kitchen_planned_total: int | None = Field(
        None,
        ge=0,
        description="已废弃，恒为 null；日总份数请使用 today_menu_day_total_stock",
    )
    tomorrow_leave_members: int = Field(..., description="明日请假会员数")
    tomorrow_meals_to_prepare: int = Field(..., description="明日需准备餐品份数")
    today_expire_one_unit_members: int = Field(
        ...,
        ge=0,
        description="锚定日已消费殆尽的末次出餐份数（到家；份数非人数，字段名历史沿用 members）：sum(当日末次配送扣次份数)，供后厨核对",
    )
    today_single_retail_total_quantity: int = Field(
        ...,
        ge=0,
        description="锚定日已支付单次零售订单份数合计（sum(single_meal_orders.quantity)）",
    )
    tomorrow_single_retail_total_quantity: int = Field(
        ...,
        ge=0,
        description="锚定日次日（明日）已支付单次零售订单份数合计，口径与 today_single_retail_total_quantity 一致",
    )
    total_members: int = Field(
        ...,
        ge=0,
        description="门店内未删除会员总户数（含周/月/次卡及未标注套餐者）；与配送大表接口同源，为当前库实时值",
    )
    active_weekly_members: int = Field(
        ...,
        ge=0,
        description="周卡且 balance>0，与会员列表 validity=active 一致",
    )
    expired_weekly_members: int = Field(
        ...,
        ge=0,
        description="周卡且 balance=0",
    )
    active_monthly_members: int = Field(
        ...,
        ge=0,
        description="月卡且 balance>0",
    )
    expired_monthly_members: int = Field(
        ...,
        ge=0,
        description="月卡且 balance=0",
    )
    weekly_card_reorder_members: int = Field(
        ...,
        ge=0,
        description="周卡：二次及以上「已缴且已入账」工单的去重会员数（续卡率分子，含提前续卡）",
    )
    weekly_card_reorder_base_members: int = Field(
        ...,
        ge=0,
        description="周卡：曾有过「已缴且已入账」工单的去重会员数（续卡率分母）",
    )
    monthly_card_reorder_members: int = Field(
        ...,
        ge=0,
        description="月卡：二次及以上「已缴且已入账」工单的去重会员数（续卡率分子，含提前续卡）",
    )
    monthly_card_reorder_base_members: int = Field(
        ...,
        ge=0,
        description="月卡：曾有过「已缴且已入账」工单的去重会员数（续卡率分母）",
    )
    tomorrow_first_meal_new_members: int = Field(
        ...,
        ge=0,
        description="明日首餐新客人数：起送业务日恰为锚定日之次日，且次日应履约（到家+自提，与大表一致）",
    )
    today_meals_week_over_week_caption: str = Field(
        ...,
        description="「今日」(锚定日) 备餐份数周同比文案，如「较上周+12」「较上周持平」",
    )
    tomorrow_meals_week_over_week_caption: str = Field(
        ...,
        description="「明日」(锚定日次日) 备餐份数周同比文案，如「较上周+12」「较上周持平」",
    )
    today_menu_day_total_stock: int | None = Field(
        None,
        ge=0,
        description="锚定日周菜单槽位「日总份数」；未排菜或未配置则为 null",
    )
    tomorrow_menu_day_total_stock: int | None = Field(
        None,
        ge=0,
        description="锚定日次日周菜单槽位「日总份数」；未排菜或未配置则为 null",
    )
    day_after_tomorrow_menu_day_total_stock: int | None = Field(
        None,
        ge=0,
        description="锚定日后天（次日+1）周菜单槽位「日总份数」；未排菜或未配置则为 null",
    )
    today_prep_metrics: DashboardDayPrepMetricsOut = Field(
        ...,
        description="锚定日备餐拆分/履约/到家配送点数（与大表同源，无需再拉 delivery-sheet）",
    )
    tomorrow_prep_metrics: DashboardDayPrepMetricsOut = Field(
        ...,
        description="锚定日次日备餐拆分/履约/到家配送点数",
    )
    from_snapshot: bool = Field(False, description="过去日：是否直接读取 admin_dashboard_biz_day_snapshots")
    snapshot_recorded_at: datetime | None = Field(
        None, description="归档写入时间；当日实时计算时通常为空（过去日首算写入后同次响应亦可为空）"
    )


class AdminKitchenPlanUpsertIn(BaseModel):
    """后厨快捷设定：写入锚定日周菜单槽位「日总份数」。"""

    business_date: date = Field(..., description="上海业务日，通常与营业概览锚定日一致")
    planned_total: int = Field(..., ge=0, le=99999, description="日总份数（与本周菜单配置同源）")


class AdminDashboardSummaryApiOut(BaseModel):
    """``GET /api/admin/dashboard-summary`` 标准成功包（便于 OpenAPI 展示完整 data 字段）。"""

    code: int = Field(200, description="业务状态码")
    data: DashboardMealSummaryOut
    msg: str = Field(..., description="提示文案")


class FinanceReceivedBucketOut(BaseModel):
    """已收账款：单业务来源的笔数与金额。"""

    count: int = Field(..., ge=0, description="笔数")
    amount_yuan: Decimal = Field(
        ...,
        ge=0,
        max_digits=14,
        decimal_places=2,
        description="实收金额合计（元）；未填金额的工单在笔数中计入，金额按 0",
    )


class MemberMembershipRefundConsumptionRowOut(BaseModel):
    """退卡预览：单日消费按菜单单价扣款明细。"""

    delivery_date: date = Field(..., description="配送业务日")
    meal_units: int = Field(..., ge=1, description="该日消费份数")
    dish_name: str | None = Field(None, description="当日菜单菜品")
    unit_price_yuan: Decimal = Field(..., ge=0, max_digits=14, decimal_places=2, description="当日菜单单价")
    line_total_yuan: Decimal = Field(..., ge=0, max_digits=14, decimal_places=2, description="该日扣款小计")


class MemberMembershipRefundPreviewOut(BaseModel):
    """会员退卡退款预览：实收 − 各消费日菜单单价扣款。"""

    member_id: int = Field(..., ge=1)
    member_name: str | None = None
    member_phone: str | None = None
    plan_type: str | None = None
    meals_consumed: int = Field(..., ge=0, description="已消费份数（配送扣次）")
    meals_remaining: int = Field(..., ge=0, description="可退剩余次数")
    meal_quota_total: int = Field(..., ge=0, description="累计总次数")
    paid_total_yuan: Decimal = Field(..., ge=0, max_digits=14, decimal_places=2, description="已入账开卡实收合计")
    consumed_value_yuan: Decimal = Field(..., ge=0, max_digits=14, decimal_places=2, description="已消费扣款（按各日菜单单价）")
    consumption_items: list[MemberMembershipRefundConsumptionRowOut] = Field(
        default_factory=list,
        description="按消费日列出的菜单扣款明细",
    )
    refund_amount_yuan: Decimal = Field(..., ge=0, max_digits=14, decimal_places=2, description="应退金额 = 实收 − 已消费扣款")


class MemberMembershipRefundConfirmIn(BaseModel):
    """确认退卡退款：金额须与预览一致。"""

    confirm_refund_yuan: Decimal = Field(..., ge=0, max_digits=14, decimal_places=2, description="确认应退金额（元）")
    remark: str | None = Field(None, max_length=500, description="退卡备注（线下退款说明等）")


class FinanceReceivedWindowOut(BaseModel):
    """某一统计窗口内：开卡工单已缴 + 单次点餐已支付 − 会员退卡退款。"""

    total_amount_yuan: Decimal = Field(..., ge=0, max_digits=14, decimal_places=2, description="已收毛额")
    total_count: int = Field(..., ge=0, description="已收笔数合计")
    card_orders: FinanceReceivedBucketOut = Field(..., description="开卡工单 pay_status=已缴（含全部卡型）")
    card_orders_weekly: FinanceReceivedBucketOut = Field(
        ...,
        description="开卡工单中卡型为周卡的笔数与实收",
    )
    card_orders_monthly: FinanceReceivedBucketOut = Field(
        ...,
        description="开卡工单中卡型为月卡的笔数与实收",
    )
    single_meal_orders: FinanceReceivedBucketOut = Field(..., description="单次点餐 pay_status=已支付")
    membership_refunds: FinanceReceivedBucketOut = Field(
        ...,
        description="会员退卡退款（按退卡确认时刻 created_at 落入窗口）",
    )
    net_total_amount_yuan: Decimal = Field(
        ...,
        max_digits=14,
        decimal_places=2,
        description="净收入 = 已收毛额 − 会员退卡退款",
    )


class FinanceReceivedSummaryOut(BaseModel):
    """财务中心：累计 / 本月（上海自然月）/ 今日（上海自然日）已收汇总。"""

    timezone_label: str = Field(default="Asia/Shanghai", description="日历与日界口径")
    shanghai_today: date = Field(..., description="请求时的上海日历日")
    shanghai_calendar_month: str = Field(..., description="当前上海自然月，YYYY-MM")
    cumulative: FinanceReceivedWindowOut = Field(..., description="历史全部已标记已收")
    this_month: FinanceReceivedWindowOut = Field(..., description="本月内（按 updated_at 落入上海月界）")
    today: FinanceReceivedWindowOut = Field(..., description="今日内（按 updated_at 落入上海日界）")


class FinanceReceivedMonthOut(BaseModel):
    """财务中心：指定上海自然月已收汇总（与 received-summary 月窗口口径一致）。"""

    calendar_month: str = Field(..., description="查询月份 YYYY-MM（上海自然月）")
    timezone_label: str = Field(default="Asia/Shanghai", description="日历与日界口径")
    window: FinanceReceivedWindowOut = Field(..., description="该月内已收窗口统计")


class FinanceReceivedDayOut(BaseModel):
    """财务中心：指定上海自然日已收汇总（与 received-summary 的 today 口径一致）。"""

    calendar_date: date = Field(..., description="查询日期（上海日历日）")
    timezone_label: str = Field(default="Asia/Shanghai", description="日历与日界口径")
    window: FinanceReceivedWindowOut = Field(..., description="该日内已收窗口统计")


class FinanceTodayPaidCardOrderRowOut(BaseModel):
    """当日已缴开卡工单明细一行（归属日与汇总同为：工单 updated_at 换算后是否落入上海自然日）。"""

    order_id: int = Field(..., ge=1, description="开卡工单 id")
    time_hm: str = Field(..., description="上海时间 HH:MM（由 updated_at 换算）")
    card_kind: str = Field(..., description="周卡 / 月卡 / 次卡")
    amount_yuan: Decimal = Field(
        ...,
        ge=0,
        max_digits=14,
        decimal_places=2,
        description="实收（元）；工单未填金额时按 0",
    )


class FinanceTodayPaidCardOrdersOut(BaseModel):
    """今日已缴开卡工单明细（微信、线下、后台标记已缴等凡 pay_status=已缴 且落入今日者）。"""

    shanghai_today: date = Field(..., description="列表对应的上海日历日")
    items: list[FinanceTodayPaidCardOrderRowOut] = Field(default_factory=list)


class DeliverySheetMemberOut(BaseModel):
    member_id: int = Field(..., ge=1, description="会员主键，供大表人工标记")
    phone: str
    name: str
    plan_type: str | None = Field(None, description="套餐类型：次卡 / 周卡 / 月卡")
    daily_meal_units: int = Field(1, ge=1, description="该会员当日计入份数")
    balance: int = Field(0, ge=0, description="会员剩余次数（核销后扣减）")
    meal_quota_total: int = Field(
        0,
        ge=0,
        description="周/月卡累计总次数；次卡或与 balance 同源时为 0",
    )
    remarks: str | None = None
    area_issue: bool = Field(False, description="会员主档或默认地址片区为空、未分配或与启用区域表不一致")
    is_delivered: bool = Field(
        False,
        description="该业务日 delivery_logs 为已送达（骑手或管理员手标；门店自提同口径）",
    )


class AdminDeliveryMarkIn(BaseModel):
    member_id: int = Field(..., ge=1)
    delivery_date: date
    kind: Literal["home", "pickup"] = Field(
        ...,
        description="home=配送到家已送达；pickup=门店自提已取/已完成",
    )


class DeliverySheetStopOut(BaseModel):
    """同一收件地址聚合为一配送点；meal_count 为当日该址份数。"""

    meal_count: int = Field(..., ge=1)
    pending_meal_count: int = Field(
        ...,
        ge=0,
        description="配送到家/门店自提：该点未确认份数；自提大表为待自提/待标记",
    )
    delivered_meal_count: int = Field(
        ...,
        ge=0,
        description="该配送点已确认送达的份数；门店自提为已自提/已标记份数",
    )
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
    pending_meal_total: int = Field(
        0,
        ge=0,
        description="本片区分组未确认送达/未自提份数合计",
    )
    delivered_meal_total: int = Field(
        0,
        ge=0,
        description="本片区分组已确认送达/已自提份数合计",
    )
    has_area_issue: bool = Field(False, description="本片区分组存在区域待处理记录")


class DeliverySheetOut(BaseModel):
    delivery_date: str
    groups: list[DeliverySheetGroupOut]
    active_regions: list[str] = Field(
        default_factory=list,
        description="delivery_regions 中 is_active=1 的名称列表，与筛选下拉同源",
    )
    home_pending_meal_total: int = Field(
        0,
        ge=0,
        description="配送到家（非门店自提分组）未确认送达份数合计",
    )
    home_delivered_meal_total: int = Field(
        0,
        ge=0,
        description="配送到家已确认送达份数合计",
    )
    pickup_meal_total: int = Field(
        0,
        ge=0,
        description="门店自提分组份数合计；不参与骑手到家送达统计",
    )
    is_subscription_delivery_day: bool = Field(
        True,
        description="该日是否视为订阅配送业务日；false 时（周日/法定及调休等）不生成列表，大表为空属正常",
    )
    total_members: int = Field(
        0,
        ge=0,
        description="门店内未删除会员总户数（含周/月/次卡及未标注套餐者）",
    )
    active_weekly_members: int = Field(
        0,
        ge=0,
        description="周卡且剩余次数 balance>0，与会员列表 validity=active 口径一致",
    )
    expired_weekly_members: int = Field(
        0,
        ge=0,
        description="周卡且 balance=0",
    )
    active_monthly_members: int = Field(
        0,
        ge=0,
        description="月卡且 balance>0",
    )
    expired_monthly_members: int = Field(
        0,
        ge=0,
        description="月卡且 balance=0",
    )


class CardOrderDeliveryAddressIn(BaseModel):
    """新建开卡工单时可选：与小程序地址字段对齐，写入会员默认配送地址并自动划区。"""

    contact_phone: str | None = Field(
        None,
        max_length=20,
        description="收货手机号；不传则使用工单上的会员手机号",
    )
    lng: float = Field(..., ge=-180, le=180, description="GCJ-02 经度（高德）")
    lat: float = Field(..., ge=-90, le=90, description="GCJ-02 纬度（高德）")
    map_location_text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="地图定位/POI 文案，对应 member_addresses.map_location_text",
    )
    door_detail: str | None = Field(
        None,
        max_length=500,
        description="门牌号、单元楼层等，对应 member_addresses.door_detail",
    )


class CardOrderCreateIn(BaseModel):
    phone: str = Field(..., min_length=5, max_length=20)
    open_mode: CardOpenMode = Field(
        CardOpenMode.NEW_MEMBER,
        description="新会员开卡：可写姓名/微信；老会员续卡：仅手机号匹配，不覆盖档案",
    )
    # 开卡时一并写入会员档案（与小程序 wechat_name / name 同源）
    name: str | None = Field(
        None,
        max_length=100,
        description="会员姓名：有值则创建工单前写入 members.name",
    )
    wechat_name: str | None = Field(
        None,
        max_length=100,
        description="微信昵称：有值则写入 members.wechat_name；传空串可清空",
    )
    delivery_start_date: date | None = Field(
        None,
        description="起送业务日（上海）；空表示暂不开卡：已缴入账仍加次数/套餐，但不写会员起送日、不强制激活",
    )
    card_kind: CardOrderKind
    pay_channel: CardPayChannel
    pay_status: CardOrderPayStatus = CardOrderPayStatus.UNPAID
    amount_yuan: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    remark: str | None = Field(None, max_length=500)
    sync_member: bool = Field(
        False,
        description="已废弃：缴费状态为「已缴」时创建工单将自动同步次数与套餐，无需再传",
    )
    delivery_address: CardOrderDeliveryAddressIn | None = Field(
        None,
        description="可选；有值时创建工单后 upsert 会员默认配送地址（含经纬度、门牌、划区）",
    )


class CardOrderPatchIn(BaseModel):
    delivery_start_date: date | None = None
    card_kind: CardOrderKind | None = Field(
        None,
        description="未入账前可更正卡类型；已同步的工单不可改，以免与已入次数不一致",
    )
    pay_status: CardOrderPayStatus | None = None
    pay_channel: CardPayChannel | None = None
    amount_yuan: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    remark: str | None = Field(None, max_length=500)
    sync_member: bool = Field(
        False,
        description="为 true 时在保存后执行同步入账（写入会员次数/套餐）；默认仅更新工单字段",
    )


class SfSameCityRowBase(BaseModel):
    """
    与顺丰 Excel 模板及弹窗行一致；提交推单时回传，后端再组 createorder。

    注意：保价为真时须带 ``goods_value_yuan``；非立即推单须带 ``expect_delivery_at``（上海时区，无时区时按上海本地处理）。
    """

    stop_id: str = Field(..., min_length=8, max_length=64, description="停靠点 id，与预览一致")
    pickup_phone: str = Field(..., max_length=20, description="取货联系电话：映射 shop/模板")
    map_location_text: str = Field(
        default="",
        max_length=500,
        description="与 member_addresses.map_location_text 一致；管理端可编辑，提交时与 recv_address 同步",
    )
    door_detail: str = Field(
        default="",
        max_length=500,
        description="与 member_addresses.door_detail 一致；管理端可编辑，提交时与 recv_building 同步",
    )
    recv_address: str = Field(
        default="",
        max_length=500,
        description="收货大地址(小区/路段)，可与楼号/门牌拆分；与 map_location_text 同源",
    )
    recv_building: str = Field(default="", max_length=500, description="楼号-门牌等；与 door_detail 同源")
    recv_name: str = Field(default="", max_length=100, description="收货人姓名")
    recv_phone: str = Field(default="", max_length=20, description="收货人电话")
    recv_lng: float | None = Field(
        None,
        ge=-180,
        le=180,
        description="收货经度 GCJ-02；写入顺丰 receive.user_lng，缺省则回退示例坐标",
    )
    recv_lat: float | None = Field(
        None,
        ge=-90,
        le=90,
        description="收货纬度 GCJ-02；写入顺丰 receive.user_lat，缺省则回退示例坐标",
    )
    product_category: str = Field(
        default="外部落地配",
        max_length=200,
        description="商品/品类显示名，写入 product_detail 与备注",
    )
    weight_kg: float = Field(..., ge=0.01, le=200.0, description="重量(Kg)，将换算为 weight_gram")
    push_immediately: bool = Field(
        False, description="否=预约单（默认）；是=立即推单（非预约，不传 expect_time）"
    )
    expect_delivery_at: datetime | None = Field(
        default=None, description="期望送达时间(上海)；非立即时必传"
    )
    remark: str | None = Field(None, max_length=2000, description="订单备注(骑士可见)")
    is_direct: bool = Field(
        False, description="专人直送，映射 is_person_direct"
    )
    vehicle_type: str = Field(
        "小轿车",
        max_length=50,
        description="车型展示名（备注文案）；顺丰接口根字段 vehicle_type 使用配置 SF_VEHICLE_TYPE_CODE（默认 1）",
    )
    is_insured: bool = Field(False, description="是否保价")
    goods_value_yuan: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2, description="保价时货值(元)"
    )
    subscription_pending_units: int = Field(0, ge=0, description="订阅本点未送达份数(预览写入)")
    single_meal_count: int = Field(0, ge=0, description="当日本点单点餐份数(预览写入)")


class SfSameCityPreviewRow(SfSameCityRowBase):
    """预览：默认全选、展示是否已推成功。"""

    group_area: str = ""
    address_line: str = Field(
        default="",
        description="不含片区前缀的详细地址行（与配送大表「片区+详细」区分，用于顺丰弹窗/快照展示）",
    )
    selected: bool = True
    already_pushed: bool = False


class SfSameCityPreviewOut(BaseModel):
    delivery_date: str
    rows: list[SfSameCityPreviewRow] = Field(default_factory=list)
    sf_configured: bool = False


class SfSameCityPushIn(BaseModel):
    """推单：逐行回传，仅 ``selected`` 为真的行会调用顺丰。"""

    delivery_date: date
    rows: list[SfSameCityPreviewRow] = Field(..., min_length=1)


class SfSameCityPushItemResult(BaseModel):
    stop_id: str
    ok: bool
    message: str
    sf_order_id: str | None = None


class SfSameCityPushOut(BaseModel):
    results: list[SfSameCityPushItemResult] = Field(default_factory=list)
    hint: str | None = Field(
        default=None,
        description="批次级提示（如顺丰预付费余额不足），便于前端统一弹窗",
    )


class SfSameCityPushRetryOut(BaseModel):
    """失败创单记录在监控页重试后的结果（单停靠点）。"""

    stop_id: str
    ok: bool
    message: str
    sf_order_id: str | None = None


class SfSameCityPushMonitorMemberRow(BaseModel):
    """监控页：停靠点对应的系统会员（订阅行 + 单点餐）；无匹配时可能来自快照收件人。"""

    member_id: int | None = None
    name: str = ""
    phone: str = ""
    kind: str = Field(
        default="subscription",
        description="subscription=订阅停靠点；single_meal=单点餐；snapshot=仅快照收件人（无法解析停靠点聚合时）",
    )


class SfSameCityPushMonitorRow(BaseModel):
    """顺丰推单列表：订单监控页，与同城创单落地库字段一致。"""

    id: int
    store_id: int = Field(default=1, description="门店 id，与推单行一致")
    delivery_date: str
    stop_id: str
    push_kind: str = Field(
        default="delivery_sheet",
        description="delivery_sheet=大表停靠点合并；single_meal_retail=订单管理单次零售推顺丰",
    )
    push_kind_label: str = Field(default="", description="订单类别展示文案")
    shop_order_id: str
    sf_order_id: str | None
    sf_bill_id: str | None
    error_code: int | None
    error_msg: str | None = None
    created_at: str | None = None
    last_callback_at: str | None = None
    last_callback_kind: str | None = None
    sf_callback_order_status: int | None = None
    merchant_cancel_requested_at: str | None = Field(
        None, description="管理端发起顺丰取消配送成功的时间（UTC ISO）；顺丰回调仍会刷新配送状态"
    )
    sf_create_status_label: str = Field(..., description="监控列表「创单状态」展示文案")
    members: list[SfSameCityPushMonitorMemberRow] = Field(
        default_factory=list,
        description="该顺丰单停靠点在当前系统聚合中的会员明细（可多人物流合并）",
    )


class SfSameCityCancelIn(BaseModel):
    """调用顺丰 ``cancelorder`` 的可选参数。"""

    cancel_reason: str | None = Field(
        None,
        max_length=200,
        description="取消原因；不传则按顺丰侧默认「商家发起取消」语义发送",
    )


class SfSameCityCancelOut(BaseModel):
    message: str = ""
    sf_response: dict[str, Any] | None = Field(None, description="顺丰接口原始 JSON")


class CardOrderOut(BaseModel):
    id: int
    member_id: int
    member_phone: str
    member_name: str
    member_wechat_name: str | None = Field(None, description="会员微信昵称")
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
    membership_template_id: int | None = Field(
        None, description="会员卡模版 id；经典周/月/次卡手工工单通常为 null"
    )
    template_product_label: str | None = Field(
        None, description="商城卡包展示文案：模版名称（种类）"
    )


TenantManagedAdminRole = Literal["full", "delivery", "support"]


class PlatformTenantOut(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: str
    store_count: int = 0
    admin_count: int = 0


class PlatformTenantCreateIn(BaseModel):
    name: str = Field(..., max_length=128)
    is_active: bool = True


class PlatformTenantPatchIn(BaseModel):
    name: str | None = Field(None, max_length=128)
    is_active: bool | None = None


class PlatformTenantAdminOut(BaseModel):
    id: int
    tenant_id: int
    username: str
    role: str
    is_active: bool
    created_at: str


class PlatformTenantAdminCreateIn(BaseModel):
    username: str = Field(..., max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    role: TenantManagedAdminRole = "full"


class PlatformTenantAdminPatchIn(BaseModel):
    password: str | None = Field(None, min_length=6, max_length=128)
    role: TenantManagedAdminRole | None = None
    is_active: bool | None = None


class PlatformSystemOverviewOut(BaseModel):
    """全库规模统计（平台管理员）。"""

    tenants_total: int
    tenants_active: int
    stores_total: int
    stores_active: int
    admin_users_active: int


class PlatformStoreOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    is_active: bool
    leave_deadline_time: str = Field("", description="HH:MM:SS")
    sf_nightly_auto_push_enabled: bool = Field(
        False,
        description="是否启用每日 08:50 自动顺丰推单（当日业务日配送大表；单次零售手动）",
    )
    created_at: str


class PlatformStoreCreateIn(BaseModel):
    name: str = Field(..., max_length=128)
    leave_deadline_time: str = Field(
        "21:00:00",
        max_length=16,
        description="当日请假截止时间，如 21:00 或 21:00:00",
    )
    is_active: bool = True
    sf_nightly_auto_push_enabled: bool = Field(
        False,
        description="启用后系统于每日 08:50（上海）自动推送当日配送大表订单至顺丰；单次零售请在订单管理手动推单",
    )


class PlatformStorePatchIn(BaseModel):
    """平台管理员 PATCH 门店；仅传需修改的字段。"""

    name: str | None = Field(None, max_length=128)
    leave_deadline_time: str | None = Field(
        None,
        max_length=16,
        description="当日请假截止时间，如 21:00 或 21:00:00",
    )
    is_active: bool | None = None
    sf_nightly_auto_push_enabled: bool | None = None


class SfSameCityPushStatsBreakdownOut(BaseModel):
    """按订单类别拆分的推单统计。"""

    total: int = 0
    success: int = 0
    failed: int = 0
    cancelled: int = Field(0, description="取消订单：商户发起取消或顺丰回调为取消/撤单(2/22)")


class SfSameCityPushStatsOut(BaseModel):
    """按配送业务日（与 ``sf_same_city_pushes.delivery_date`` 一致）统计推单条数。"""

    delivery_date: str = Field(..., description="配送业务日 YYYY-MM-DD")
    total: int
    success: int
    failed: int
    cancelled: int = Field(0, description="取消订单：商户发起取消或顺丰回调为取消/撤单(2/22)")
    delivery_sheet: SfSameCityPushStatsBreakdownOut = Field(
        default_factory=SfSameCityPushStatsBreakdownOut,
        description="大表合并（delivery_sheet）",
    )
    single_meal_retail: SfSameCityPushStatsBreakdownOut = Field(
        default_factory=SfSameCityPushStatsBreakdownOut,
        description="单次零售（single_meal_retail）",
    )


class AdminSystemNotificationOut(BaseModel):
    """管理端系统消息（如顺丰自动推单每日摘要）。"""

    id: int
    store_id: int
    kind: str
    business_date: str
    delivery_date: str = Field(
        default="",
        description="单次零售消息解析出的供餐日；其它 kind 为空",
    )
    title: str
    message: str
    total: int = 0
    success: int = 0
    failed: int = 0
    skip_reason: str | None = None
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    created_at: str | None = None


class AdminSystemNotificationListOut(BaseModel):
    items: list[AdminSystemNotificationOut] = Field(default_factory=list)
    unacknowledged_count: int = 0


class TenantIntegrationSettingsOut(BaseModel):
    """租户对接配置（密钥仅以是否已设置展示，不回显明文）。"""

    tenant_id: int
    wx_mini_appid: str | None = None
    wx_mini_secret_set: bool = False
    wechat_pay_mch_id: str | None = None
    wechat_pay_api_key_set: bool = False
    wechat_pay_notify_url: str | None = None
    wechat_pay_ssl_cert_path: str | None = Field(
        None, description="微信退款 apiclient_cert.pem 路径；空则回退门店或全局 .env"
    )
    wechat_pay_ssl_key_path: str | None = Field(
        None, description="微信退款 apiclient_key.pem 路径；空则回退门店或全局 .env"
    )
    wx_subscribe_delivery_tmpl_id: str | None = None
    wx_subscribe_renew_tmpl_id: str | None = None
    sf_open_dev_id: int | None = None
    sf_open_secret_set: bool = False
    sf_open_shop_id: str | None = None
    sf_open_shop_type: int | None = None
    sf_pickup_phone: str | None = None
    sf_pickup_address: str | None = None
    sf_city_name: str | None = None
    extra_json: str | None = Field(None, description="扩展 JSON，预留其它对接字段")
    updated_at: str = ""


class TenantIntegrationSettingsPatchIn(BaseModel):
    wx_mini_appid: str | None = Field(None, max_length=64)
    wx_mini_secret: str | None = Field(None, max_length=128, description="传空字符串表示清除租户覆盖")
    wechat_pay_mch_id: str | None = Field(None, max_length=32)
    wechat_pay_api_key: str | None = Field(None, max_length=128)
    wechat_pay_notify_url: str | None = Field(None, max_length=512)
    wechat_pay_ssl_cert_path: str | None = Field(None, max_length=512, description="退款证书 cert 路径；空串清除租户默认")
    wechat_pay_ssl_key_path: str | None = Field(None, max_length=512, description="退款证书 key 路径；空串清除租户默认")
    wx_subscribe_delivery_tmpl_id: str | None = Field(None, max_length=128)
    wx_subscribe_renew_tmpl_id: str | None = Field(None, max_length=128)
    sf_open_dev_id: int | None = Field(None, ge=0)
    sf_open_secret: str | None = Field(None, max_length=255)
    sf_open_shop_id: str | None = Field(None, max_length=64)
    sf_open_shop_type: int | None = Field(None, ge=1, le=2)
    sf_pickup_phone: str | None = Field(None, max_length=32)
    sf_pickup_address: str | None = Field(None, max_length=512)
    sf_city_name: str | None = Field(None, max_length=64)
    extra_json: str | None = Field(None, description="JSON 字符串；空字符串清除")
