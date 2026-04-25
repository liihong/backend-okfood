from datetime import date

from app.models.member import Member


def is_absent_on_delivery_date(member: Member, delivery_date: date, *, today: date) -> bool:
    """
    判断会员在指定配送日是否视为「请假/不配送」。

    规则：
    - 长期区间：leave_range_start ~ leave_range_end 闭区间命中即缺席；
    - 「仅明天请假」：与 members 表一致，须 **仍勾选** is_leaved_tomorrow 且 tomorrow_leave_target_date
      有值时，仅该业务日缺席；无 target 时回退为配送日=业务今天+1（旧数据）。
    - 已撤销但 target 未清理的脏数据：不按 target 判缺席，避免大表/骑手误排除。
    """
    if member.leave_range_start and member.leave_range_end:
        if member.leave_range_start <= delivery_date <= member.leave_range_end:
            return True
    if member.tomorrow_leave_target_date is not None and member.is_leaved_tomorrow:
        return delivery_date == member.tomorrow_leave_target_date
    if member.is_leaved_tomorrow and member.tomorrow_leave_target_date is None:
        tomorrow = date.fromordinal(today.toordinal() + 1)
        return delivery_date == tomorrow
    return False


def is_leave_deadline_passed(now_time, deadline) -> bool:
    """当前时间是否已超过「当日请假截止」时刻（仅比较 time）。"""
    return now_time > deadline
