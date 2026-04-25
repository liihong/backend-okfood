import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, update

from app.core.config import settings
from app.core.timeutil import today_shanghai
from app.db.session import SessionLocal
from app.models.member import Member

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def job_reset_leave_flags() -> None:
    """
    每日 00:01：清理「明日请假」——带 target 的业务日若已小于当前业务日则清空；
    无 target 的旧数据仍全量清空 is_leaved_tomorrow（与旧版跨日 0:01 一致）；清理已过期的长期请假区间。
    业务日统一使用 Asia/Shanghai。
    """
    db = SessionLocal()
    try:
        today: date = today_shanghai()
        db.execute(
            update(Member)
            .where(
                Member.tomorrow_leave_target_date.isnot(None),
                Member.tomorrow_leave_target_date < today,
            )
            .values(is_leaved_tomorrow=False, tomorrow_leave_target_date=None)
        )
        db.execute(
            update(Member)
            .where(
                Member.tomorrow_leave_target_date.is_(None),
                Member.is_leaved_tomorrow.is_(True),
            )
            .values(is_leaved_tomorrow=False)
        )
        # 已撤销仅明日但 target 残留：清 target，避免历史脏数据与配送名单再次偏离
        db.execute(
            update(Member)
            .where(
                Member.is_leaved_tomorrow.is_(False),
                Member.tomorrow_leave_target_date.isnot(None),
            )
            .values(tomorrow_leave_target_date=None)
        )
        rows = db.scalars(select(Member).where(Member.leave_range_end.isnot(None))).all()
        for m in rows:
            if m.leave_range_end is not None and m.leave_range_end < today:
                m.leave_range_start = None
                m.leave_range_end = None
        db.commit()
        logger.info("请假标记重置任务完成: today=%s", today.isoformat())
    except Exception:
        logger.exception("请假标记重置任务失败")
        db.rollback()
    finally:
        db.close()


def job_low_balance_notify() -> None:
    """
    每日 18:00：低余额扫描。微信模板未接入前仅记录日志，并写入去重字段避免重复提醒。
    """
    db = SessionLocal()
    try:
        today = today_shanghai()
        threshold = settings.LOW_BALANCE_THRESHOLD
        stmt = select(Member).where(Member.is_active.is_(True), Member.balance <= threshold)
        rows = db.scalars(stmt).all()
        for m in rows:
            if m.last_low_balance_notify_date == today:
                continue
            logger.info(
                "低余额提醒占位: phone=%s balance=%s (可在此接入微信模板)",
                m.phone[:3] + "****" + m.phone[-4:] if len(m.phone) >= 7 else "***",
                m.balance,
            )
            m.last_low_balance_notify_date = today
        db.commit()
    except Exception:
        logger.exception("低余额扫描任务失败")
        db.rollback()
    finally:
        db.close()


def setup_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(job_reset_leave_flags, "cron", hour=0, minute=1, id="reset_leave", replace_existing=True)
    scheduler.add_job(job_low_balance_notify, "cron", hour=18, minute=0, id="low_balance", replace_existing=True)
    scheduler.start()


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
