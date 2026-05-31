from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# 业务日与时区：与定时任务、请假截止、菜单「明天」及运营对齐时间口径均为北京时间（Asia/Shanghai）。
# 库内 DATETIME 列统一存「北京时间」naive（无时区，与 Asia/Shanghai 墙钟一致）；入库请用 ``beijing_now_naive()``。
TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


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
    """会员起送业务日允许选择的最早日期（上海）：当天不可选，最早为「明天」。

    小程序完善/修改配送信息、开卡工单起送日写入等均与此口径一致；当日订单走单次点餐等其它入口。
    """
    n = now if now is not None else now_shanghai()
    t = n.date()
    return t.fromordinal(t.toordinal() + 1)


def min_leave_start_shanghai(now: datetime | None = None) -> date:
    """会员自助请假允许的最早业务日（上海）：跨日后不可请「当日」假，最早为明天。"""
    n = now if now is not None else now_shanghai()
    t = n.date()
    return t.fromordinal(t.toordinal() + 1)


def shanghai_naive_range_for_calendar_day(d: date) -> tuple[datetime, datetime]:
    """上海自然日 [d 00:00, 次日 00:00)（左闭右开），墙钟与 Asia/Shanghai 一致。

    适用于库内 **北京时间 naive** 的 ``created_at`` / ``updated_at`` 等列按业务日筛选。
    """
    start = datetime.combine(d, time.min)
    return start, start + timedelta(days=1)


def shanghai_naive_range_for_calendar_month(year: int, month: int) -> tuple[datetime, datetime]:
    """上海自然月 [当月1日 00:00, 次月1日 00:00) 的北京时间 naive 区间（左闭右开）。"""
    first = date(year, month, 1)
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    start = datetime.combine(first, time.min)
    end = datetime.combine(next_first, time.min)
    return start, end


def format_beijing_naive_hm(dt: datetime) -> str:
    """库内北京时间 naive → ``HH:MM`` 展示。"""
    return dt.strftime("%H:%M")


def format_utc_naive_as_shanghai_hm(dt: datetime) -> str:
    """兼容旧名：现已统一为北京时间存库，等价于 `format_beijing_naive_hm`。"""
    return format_beijing_naive_hm(dt)
