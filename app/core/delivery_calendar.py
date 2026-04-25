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


def _is_subscription_delivery_day_with_calendar(d: date) -> bool:
    """使用 chinese-calendar 的判定；仅应在库支持的年份上调用（见外层的 NotImplemented 降级）。"""
    if d.weekday() == 6:
        return False
    if cc.is_workday(d):
        return True
    if d.weekday() == 5:
        _, holiday_name = cc.get_holiday_detail(d)
        return holiday_name is None
    return False


def is_subscription_delivery_day(d: date) -> bool:
    """给定日期是否为会员订阅配送的履约日。"""
    try:
        return _is_subscription_delivery_day_with_calendar(d)
    except NotImplementedError:
        # 库无该年国务院安排时，is_workday 会抛错；避免接口 500。口径：至少「周日不送」，其余日先按可配送
        if d.weekday() == 6:
            return False
        return True
