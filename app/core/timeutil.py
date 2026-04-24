from datetime import date, datetime, time
from zoneinfo import ZoneInfo

# 业务日与时区：与定时任务、请假截止、菜单「明天」保持一致
TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


def now_shanghai() -> datetime:
    """当前上海时区的「带时区」时间。"""
    return datetime.now(TZ_SHANGHAI)


def today_shanghai() -> date:
    """当前业务日（上海）。"""
    return now_shanghai().date()


def tomorrow_shanghai() -> date:
    return today_shanghai().fromordinal(today_shanghai().toordinal() + 1)


def min_member_delivery_start_shanghai(now: datetime | None = None) -> date:
    """会员起送业务日允许选择的最早日期（上海）：当日 10:00 前最早为明天，10:00 及之后最早为后天。"""
    n = now if now is not None else now_shanghai()
    t = n.date()
    if n.time() >= time(10, 0, 0):
        return t.fromordinal(t.toordinal() + 2)
    return t.fromordinal(t.toordinal() + 1)
