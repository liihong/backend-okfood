from datetime import date

from app.models.member import Member


def is_absent_on_delivery_date(member: Member, delivery_date: date, *, today: date) -> bool:
    """
    判断会员在指定配送日是否视为「请假/不配送」。

    规则：
    - 长期区间：leave_range_start ~ leave_range_end 闭区间命中即缺席；
    - 「仅明天请假」：仅当配送日等于「业务今天+1天」时缺席（不影响今日配送清单）。
    """
    if member.leave_range_start and member.leave_range_end:
        if member.leave_range_start <= delivery_date <= member.leave_range_end:
            return True
    if member.is_leaved_tomorrow:
        tomorrow = date.fromordinal(today.toordinal() + 1)
        if delivery_date == tomorrow:
            return True
    return False


def is_leave_deadline_passed(now_time, deadline) -> bool:
    """当前时间是否已超过「当日请假截止」时刻（仅比较 time）。"""
    return now_time > deadline
