"""订阅配送业务日判定（上海日历）。

规则摘要：
- 周日固定不配送（含法定补班周日，仍不配送）。
- 国家法定节假日及国务院公布的调休放假日不配送（依赖 `chinese-calendar` 与国务院安排）。
- 普通周六照常配送；若周六落在长假调休范围内则不配送；若周六为补班工作日则配送。

非配送日不出现在配送大表、不派订阅单、确认送达会拒绝；会员次数不在该日扣减，相当于顺延至下一实际配送日。
"""

from __future__ import annotations

from datetime import date

import chinese_calendar as cc


def is_subscription_delivery_day(d: date) -> bool:
    """给定日期是否为会员订阅配送的履约日。"""
    # 周日一律不配送
    if d.weekday() == 6:
        return False
    # 工作日（含补班周末）配送
    if cc.is_workday(d):
        return True
    # 普通周六：非法定调休放假则仍配送
    if d.weekday() == 5:
        _, holiday_name = cc.get_holiday_detail(d)
        return holiday_name is None
    return False
