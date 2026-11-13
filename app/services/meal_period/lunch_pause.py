"""午餐单独暂停。

只给午餐应配、午餐日程和后台档案使用。
禁止写入 members.delivery_deferred，不改 is_active。
晚餐大表、晚餐扣次、请假统计、整体暂停配送不得调用本模块。
"""

from __future__ import annotations

from app.models.member import Member


def lunch_schedule_allows_delivery(*, lunch_delivery_paused: bool) -> bool:
    """这一天是否还能进入午餐配送名单。

    只看午餐暂停开关。为真表示未暂停，按原午餐规则继续判断。
    不读请假字段，不读晚餐暂停，也不等于会员整体暂停。
    """
    return not bool(lunch_delivery_paused)


def sql_lunch_not_paused():
    """午餐 SQL 名单条件：未单独暂停午餐。

    列默认否，未补丁前的旧行在补丁后仍为否，午餐统计口径不变。
    只追加到已有午餐 where，不要接到晚餐查询或请假人数查询上。
    """
    return Member.lunch_delivery_paused.is_(False)
