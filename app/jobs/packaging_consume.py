"""每天 22:00 扣当天午餐和晚餐的包装。

只编排门店和日期。份数、用盒和流水都在 packaging 服务里。
漏跑时只补昨天的两餐，更早的日期不再回补，免得和已经做过的周校对打架。
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select

from app.core.timeutil import today_shanghai
from app.db.session import SessionLocal
from app.models.store import Store
from app.services.packaging.alert_service import sync_day_alert
from app.services.packaging.consume_service import consume_meal, meal_periods_for_day

logger = logging.getLogger(__name__)


def job_packaging_daily_consume() -> None:
    """上海时间晚上跑。一个门店失败不影响其他门店。"""
    today = today_shanghai()
    yesterday = today - timedelta(days=1)
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
        for biz_date in (yesterday, today):
            _consume_store_day(int(store_id), biz_date)


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
