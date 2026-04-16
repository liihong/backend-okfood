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
