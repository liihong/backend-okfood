"""包装库存常量。

本模块不计算餐品份数，也不写会员、订单或日库存流水。
"""

from __future__ import annotations

# 流水类型。出现任意一种即视为该品已期初，晚上的自动领用才会扣它。
TXN_OPENING = "opening"
TXN_PURCHASE_IN = "purchase_in"
TXN_CONSUME = "consume"
TXN_STOCKTAKE = "stocktake"

TXN_LABELS = {
    TXN_OPENING: "期初",
    TXN_PURCHASE_IN: "入库",
    TXN_CONSUME: "自动领用",
    TXN_STOCKTAKE: "盘点",
}

# 系统消息 kind。同一门店同一天只留一条，和顺丰日摘要的写法一致。
KIND_PACKAGING_LOW_STOCK = "packaging_low_stock"

# 份数来源。kitchen=后厨出餐（含包好没卖出的）；delivered=没填日总份时退回的实发份数。
PORTION_SOURCE_KITCHEN = "kitchen"
PORTION_SOURCE_DELIVERED = "delivered"

# bag_flag 只有这一个取值。普通品必须保持 NULL，不能写成 0，否则唯一约束会把所有普通品挤成一行。
BAG_FLAG = 1

# 通知正文上限与 admin_system_notifications.message 列一致。
ALERT_MESSAGE_LIMIT = 2000

MEAL_LABELS = {"lunch": "午餐", "dinner": "晚餐"}
