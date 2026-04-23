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


class LeaveType(str, Enum):
    """请假类型：明天 / 区间 / 仅取消明天 / 取消全部请假标记。"""

    TOMORROW = "tomorrow"
    RANGE = "range"
    CLEAR_TOMORROW = "clear_tomorrow"
    CANCEL = "cancel"


class CardOrderKind(str, Enum):
    """开卡工单：套餐类型（仅周卡/月卡）。"""

    WEEK = "周卡"
    MONTH = "月卡"


class CardOpenMode(str, Enum):
    """开卡工单：新会员建档开卡 vs 老会员续卡（仅手机号匹配，不覆盖档案姓名/微信）。"""

    NEW_MEMBER = "new_member"
    RENEW = "renew"


class CardPayChannel(str, Enum):
    WECHAT = "微信"
    ALIPAY = "支付宝"
    OFFLINE = "线下"


class CardOrderPayStatus(str, Enum):
    UNPAID = "未缴"
    PAID = "已缴"
