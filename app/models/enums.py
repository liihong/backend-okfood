from enum import Enum


class PlanType(str, Enum):
    TIMES = "次卡"
    WEEK = "周卡"
    MONTH = "月卡"


class MealPeriod(str, Enum):
    """订阅履约餐段（与 plan_type 周/月/次正交）。"""

    LUNCH = "lunch"
    DINNER = "dinner"


class DeliverySheetView(str, Enum):
    """管理端配送大表视图。"""

    LUNCH = "lunch"
    DINNER = "dinner"
    LUNCH_DINNER = "lunch_dinner"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    LEAVE = "leave"


class DayStockAdjustmentReason(str, Enum):
    """日库存损耗/回补原因（客服报损耗下拉）。"""

    SPILL = "spill"
    KITCHEN_TASTE = "kitchen_taste"
    KITCHEN_WASTE = "kitchen_waste"
    COMP_MEAL = "comp_meal"
    COUNT_CORRECTION = "count_correction"
    OTHER = "other"


class BalanceReason(str, Enum):
    RECHARGE = "recharge"
    DELIVERY = "delivery"
    REFUND = "refund"
    ADMIN_ADJUST = "admin_adjust"
    SINGLE_MEAL = "single_meal"
    MEAL_COMPENSATION = "meal_compensation"


class LeaveType(str, Enum):
    """请假类型：明天 / 区间 / 仅取消明天 / 取消全部请假标记。"""

    TOMORROW = "tomorrow"
    RANGE = "range"
    CLEAR_TOMORROW = "clear_tomorrow"
    CANCEL = "cancel"


class CardOrderKind(str, Enum):
    """开卡工单：套餐类型（周卡 / 月卡 / 次卡）。"""

    WEEK = "周卡"
    MONTH = "月卡"
    TIMES = "次卡"


class CardOpenMode(str, Enum):
    """开卡工单：新会员建档开卡 vs 老会员续卡（仅手机号匹配，不覆盖档案姓名/微信）。"""

    NEW_MEMBER = "new_member"
    RENEW = "renew"


class CardOrderActivationMode(str, Enum):
    """开卡工单入账意图（落库 member_card_orders.activation_mode；NULL=legacy 推断）。"""

    EXPLICIT_DATE = "explicit_date"
    KEEP_SCHEDULE = "keep_schedule"
    DEFER_NOT_OPEN = "defer_not_open"
    DEFER_PAUSE = "defer_pause"


class MemberLifecycleCode(str, Enum):
    """会员档案只读生命周期视图（API 输出，不落 members 表）。"""

    REFUNDED = "refunded"
    CARD_NOT_OPEN = "card_not_open"
    PAUSED = "paused"
    AWAITING_SETUP = "awaiting_setup"
    BALANCE_EXHAUSTED = "balance_exhausted"
    NEVER_OPENED = "never_opened"
    RENEW_PENDING = "renew_pending"
    DELIVERING = "delivering"


class CardPayChannel(str, Enum):
    WECHAT = "微信"
    ALIPAY = "支付宝"
    OFFLINE = "线下"
    DOUYIN = "抖音"


class DouyinGrantType(str, Enum):
    """抖音团购商品映射：验券成功后发放的本地权益类型。"""

    WEEK_CARD = "week_card"
    MONTH_CARD = "month_card"
    MEMBERSHIP_TEMPLATE = "membership_template"
    COUPON_TEMPLATE = "coupon_template"
    RETAIL_PRODUCT = "retail_product"


class DouyinRedemptionStatus(str, Enum):
    """抖音验券流水状态。"""

    SUCCESS = "success"
    FAILED = "failed"
    # 抖音已核销、本地发奖尚未完成（落库后防丢单，支持断点续发奖）
    VERIFIED = "verified"
    GRANT_FAILED = "grant_failed"
    CANCELLED = "cancelled"


class CardOrderPayStatus(str, Enum):
    UNPAID = "未缴"
    PAID = "已缴"
    REFUNDED = "已退款"
    CANCELLED = "已取消"


class CouponType(str, Enum):
    """优惠券类型；MVP 仅代金券。"""

    CASH = "cash"


class CouponBizType(str, Enum):
    """适用业务线。"""

    ALL = "all"
    MEMBER_CARD = "member_card"
    SINGLE_MEAL = "single_meal"
    STORE_RETAIL = "store_retail"


class CouponScopeLevel(str, Enum):
    """业务线内细粒度适用范围。"""

    ALL = "all"
    WEEK_MONTH = "week_month"
    MEMBERSHIP_TEMPLATE = "membership_template"
    MENU_DISH = "menu_dish"
    RETAIL_CATEGORY = "retail_category"
    RETAIL_PRODUCT = "retail_product"


class CouponValidityMode(str, Enum):
    FIXED_RANGE = "fixed_range"
    DAYS_AFTER_GRANT = "days_after_grant"


# 进小程序购卡提醒：计入可用券的业务线（不含单餐/商城零售）
MEMBER_COUPON_REMINDER_BIZ_TYPES = frozenset({"all", "member_card"})


class MemberCouponStatus(str, Enum):
    AVAILABLE = "available"
    LOCKED = "locked"
    USED = "used"
    REVOKED = "revoked"
    EXPIRED = "expired"


class CouponLockedOrderBiz(str, Enum):
    MEMBER_CARD = "member_card"
    SINGLE_MEAL = "single_meal"
    STORE_RETAIL = "store_retail"
