"""每天 22:00 扣当天午餐和晚餐的包装。

只编排门店和日期。份数、用盒和流水都在 packaging 服务里。
漏跑时从「第一次入库的第二天」补到今天，最多往前 7 天。
第一次入库当天不补：那笔结存是实盘，当天已经包过的餐含在数里。
更早的日期留给每周校对，避免和已经改过的结存叠扣。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select

from app.core.timeutil import today_shanghai
from app.db.session import SessionLocal
from app.models.packaging_stock_txn import PackagingStockTxn
from app.models.store import Store
from app.services.packaging.alert_service import sync_day_alert
from app.services.packaging.consume_service import consume_meal, meal_periods_for_day

logger = logging.getLogger(__name__)

# 调度停了几天时，最多补这一窗口。已有运行记录的餐次会直接跳过，不会扣两次。
CATCHUP_DAYS = 7


def dates_to_consume(today: date, first_stock_date: date | None) -> list[date]:
    """要扣的供餐日，从早到晚。最后一天一定是今天。

    还没有入库流水时，仍跑昨天和今天：未期初的品不会改结存。
    """
    if first_stock_date is None:
        return [today - timedelta(days=1), today]
    earliest = max(first_stock_date + timedelta(days=1), today - timedelta(days=CATCHUP_DAYS))
    dates: list[date] = []
    day = earliest
    while day < today:
        dates.append(day)
        day += timedelta(days=1)
    dates.append(today)
    return dates


def job_packaging_daily_consume() -> None:
    """上海时间晚上跑。一个门店失败不影响其他门店。"""
    today = today_shanghai()
    db = SessionLocal()
    try:
        store_ids = list(
            db.scalars(select(Store.id).where(Store.is_active.is_(True)).order_by(Store.id.asc())).all()
        )
    except Exception:
        logger.exception("包装扣库读取门店失败")
        return
    finally:
        db.close()
    for store_id in store_ids:
        for biz_date in dates_to_consume(today, _first_stock_date(int(store_id))):
            _consume_store_day(int(store_id), biz_date)


def _first_stock_date(store_id: int) -> date | None:
    """没有流水就还没期初，晚上只会记一笔 0 份的运行记录。"""
    db = SessionLocal()
    try:
        found = db.scalar(
            select(func.min(PackagingStockTxn.biz_date)).where(
                PackagingStockTxn.store_id == int(store_id)
            )
        )
    except Exception:
        logger.exception("包装扣库读取期初日期失败 store=%s", store_id)
        return None
    finally:
        db.close()
    return found


def _consume_store_day(store_id: int, biz_date) -> None:
    db = SessionLocal()
    try:
        for period in meal_periods_for_day():
            try:
                consume_meal(db, store_id=store_id, biz_date=biz_date, meal_period=period)
            except Exception:
                db.rollback()
                logger.exception(
                    "包装扣库失败 store=%s date=%s period=%s", store_id, biz_date, period
                )
        try:
            sync_day_alert(db, store_id=store_id, biz_date=biz_date)
        except Exception:
            db.rollback()
            logger.exception("包装库存消息失败 store=%s date=%s", store_id, biz_date)
    finally:
        db.close()
