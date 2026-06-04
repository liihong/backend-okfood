from enum import Enum


class PlanType(str, Enum):
    TIMES = "次卡"
    WEEK = "周卡"
    MONTH = "月卡"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    LEAVE = "leave"


class BalanceReason(str, Enum):
    RECHARGE = "recharge"
    DELIVERY = "delivery"
    REFUND = "refund"
    ADMIN_ADJUST = "admin_adjust"
    SINGLE_MEAL = "single_meal"


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


class DouyinRedemptionStatus(str, Enum):
    """抖音验券流水状态。"""

    SUCCESS = "success"
    FAILED = "failed"
    GRANT_FAILED = "grant_failed"


class CardOrderPayStatus(str, Enum):
    UNPAID = "未缴"
    PAID = "已缴"
    REFUNDED = "已退款"


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
