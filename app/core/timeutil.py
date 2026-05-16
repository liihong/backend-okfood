from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# 业务日与时区：与定时任务、请假截止、菜单「明天」及运营对齐时间口径均为北京时间（Asia/Shanghai）。
TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")
TZ_UTC = ZoneInfo("UTC")


def beijing_now_naive() -> datetime:
    """当前北京时间，去掉 tzinfo（便于写入 MySQL DATETIME 等无时区列）。"""
    return now_shanghai().replace(tzinfo=None)


def now_shanghai() -> datetime:
    """当前上海时区的「带时区」时间。"""
    return datetime.now(TZ_SHANGHAI)


def today_shanghai() -> date:
    """当前业务日（上海）。"""
    return now_shanghai().date()


def tomorrow_shanghai() -> date:
    return today_shanghai().fromordinal(today_shanghai().toordinal() + 1)


def min_member_delivery_start_shanghai(now: datetime | None = None) -> date:
    """会员起送业务日允许选择的最早日期（上海）：当日 10:00 前最早为今天，10:00 及之后最早为明天。"""
    n = now if now is not None else now_shanghai()
    t = n.date()
    if n.time() >= time(10, 0, 0):
        return t.fromordinal(t.toordinal() + 1)
    return t


def utc_naive_range_for_shanghai_calendar_day(d: date) -> tuple[datetime, datetime]:
    """上海自然日 [d 00:00, 次日 00:00) 对应库内 naive UTC 时间戳区间（左闭右开）。

    适用于仍以 utcnow 写入 created_at/updated_at 的表；按上海当日筛选时使用。
    （会员操作审计日志等已改为存北京时间，勿用本函数区间去筛此类列。）
    """
    start_local = datetime.combine(d, time.min, tzinfo=TZ_SHANGHAI)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(TZ_UTC).replace(tzinfo=None)
    end_utc = end_local.astimezone(TZ_UTC).replace(tzinfo=None)
    return start_utc, end_utc


def format_utc_naive_as_shanghai_hm(dt: datetime) -> str:
    """将库内 naive UTC 的时刻转为上海时区，格式 HH:MM（用于财务日明细展示）。"""
    aware = dt.replace(tzinfo=TZ_UTC)
    return aware.astimezone(TZ_SHANGHAI).strftime("%H:%M")


def utc_naive_range_for_shanghai_calendar_month(year: int, month: int) -> tuple[datetime, datetime]:
    """上海自然月 [当月1日 00:00, 次月1日 00:00) 的 naive UTC 区间（左闭右开）。"""
    first = date(year, month, 1)
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    start_utc, _ = utc_naive_range_for_shanghai_calendar_day(first)
    _, end_utc = utc_naive_range_for_shanghai_calendar_day(next_first)
    return start_utc, end_utc
