"""礼品券常量。独立于营销代金券枚举，避免混用 status。"""

from __future__ import annotations

# 活动状态
CAMPAIGN_DRAFT = "draft"
CAMPAIGN_ACTIVE = "active"
CAMPAIGN_CLOSED = "closed"

# 资格状态：当天不在大表不得写成 skipped/revoked
ENTITLEMENT_GRANTED = "granted"
ENTITLEMENT_REDEEMED = "redeemed"
ENTITLEMENT_REVOKED = "revoked"

GRANT_SOURCE_RULE = "rule"
GRANT_SOURCE_MANUAL = "manual"

# 圈人卡型：month=月卡（不含季卡），quarter=季卡（模版种类含「季」）
PLAN_KIND_MONTH = "month"
PLAN_KIND_QUARTER = "quarter"

MATCH_ANY_IN_RANGE = "any_in_range"

# 开卡入账流水 detail 前缀，与 member_card_order_service 写入格式对齐
CARD_ORDER_CREDIT_DETAIL_PREFIX = "开卡工单#"
