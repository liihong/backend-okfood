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
                Member.deleted_at.is_(None),
                Member.tomorrow_leave_target_date.isnot(None),
                Member.tomorrow_leave_target_date < today,
            )
            .values(is_leaved_tomorrow=False, tomorrow_leave_target_date=None)
        )
        db.execute(
            update(Member)
            .where(
                Member.deleted_at.is_(None),
                Member.tomorrow_leave_target_date.is_(None),
                Member.is_leaved_tomorrow.is_(True),
            )
            .values(is_leaved_tomorrow=False)
        )
        # 已撤销仅明日但 target 残留：清 target，避免历史脏数据与配送名单再次偏离
        db.execute(
            update(Member)
            .where(
                Member.deleted_at.is_(None),
                Member.is_leaved_tomorrow.is_(False),
                Member.tomorrow_leave_target_date.isnot(None),
            )
            .values(tomorrow_leave_target_date=None)
        )
        rows = db.scalars(
            select(Member).where(Member.deleted_at.is_(None), Member.leave_range_end.isnot(None))
        ).all()
        for m in rows:
            if m.leave_range_end is not None and m.leave_range_end < today:
                m.leave_range_start = None
                m.leave_range_end = None
        from app.services.member_daily_meal_units_service import apply_all_pending_daily_meal_units

        applied_units = apply_all_pending_daily_meal_units(db)
        db.commit()
        logger.info(
            "请假标记重置任务完成: today=%s, applied_daily_meal_units=%s",
            today.isoformat(),
            applied_units,
        )
    except Exception:
        logger.exception("请假标记重置任务失败")
        db.rollback()
    finally:
        db.close()


def job_low_balance_notify() -> None:
    """
    每日 17:00（上海）：

    1. 低余额兜底：记录仍有订阅额度但未触达微信续费提醒的用户（主路径为扣次后触达）。
    2. 余量不足配送：扫描 **次日供餐日** 每日多份但剩余次数不够的会员，写入客服系统消息。
    """
    from app.core.timeutil import tomorrow_shanghai
    from app.services.admin_system_notification_service import (
        scan_insufficient_balance_delivery_notifications_for_all_stores,
    )

    db = SessionLocal()
    try:
        today = today_shanghai()
        threshold = settings.LOW_BALANCE_THRESHOLD
        stmt = select(Member).where(
            Member.deleted_at.is_(None),
            Member.is_active.is_(True),
            Member.balance <= threshold,
            Member.wx_renew_remind_quota > 0,
        )
        rows = db.scalars(stmt).all()
        for m in rows:
            if m.last_low_balance_notify_date == today:
                continue
            logger.info(
                "低余额兜底扫描: phone=%s balance=%s quota=%s（主路径为扣次触达）",
                m.phone[:3] + "****" + m.phone[-4:] if len(m.phone) >= 7 else "***",
                m.balance,
                m.wx_renew_remind_quota,
            )
        delivery_day = tomorrow_shanghai()
        n_insuff = scan_insufficient_balance_delivery_notifications_for_all_stores(
            db, business_date=delivery_day
        )
        if n_insuff:
            logger.info(
                "余量不足配送客服提醒（次日供餐日 %s）: created=%s",
                delivery_day.isoformat(),
                n_insuff,
            )
        db.commit()
    except Exception:
        logger.exception("低余额扫描任务失败")
        db.rollback()
    finally:
        db.close()


def job_expire_unpaid_single_meal_orders() -> None:
    """每 2 分钟：单次零售未支付超过 30 分钟的订单自动取消。"""
    from app.services.single_meal_order_service import expire_stale_unpaid_single_meal_orders

    db = SessionLocal()
    try:
        n = expire_stale_unpaid_single_meal_orders(db)
        if n:
            logger.info("单次零售超时未支付自动取消: count=%s", n)
    except Exception:
        logger.exception("单次零售超时未支付自动取消任务失败")
        db.rollback()
    finally:
        db.close()


def job_expire_unpaid_store_retail_orders() -> None:
    """每 2 分钟：商城零售未支付超过 30 分钟的订单自动取消。"""
    from app.services.store_retail_order_service import expire_stale_unpaid_store_retail_orders

    db = SessionLocal()
    try:
        n = expire_stale_unpaid_store_retail_orders(db)
        if n:
            logger.info("商城零售超时未支付自动取消: count=%s", n)
    except Exception:
        logger.exception("商城零售超时未支付自动取消任务失败")
        db.rollback()
    finally:
        db.close()


def job_expire_stale_unpaid_miniprogram_card_orders() -> None:
    """每 2 分钟：购卡未支付超过 30 分钟则释放 locked 券并恢复原价。"""
    from app.services.member_card_pay_service import expire_stale_unpaid_miniprogram_card_orders

    db = SessionLocal()
    try:
        n = expire_stale_unpaid_miniprogram_card_orders(db)
        if n:
            logger.info("购卡超时未支付释放优惠券: count=%s", n)
    except Exception:
        logger.exception("购卡超时未支付释放优惠券任务失败")
        db.rollback()
    finally:
        db.close()


def job_sf_nightly_auto_push() -> None:
    """
    每日 08:50（上海）：对启用「顺丰自动推单」的门店，自动推送当日业务日配送大表（订阅合并）停靠点至顺丰。
    单次零售订单不在此任务内，须订单管理手动推单。
    """
    from app.services.sf_same_city_service import run_sf_nightly_auto_push_for_all_stores

    db = SessionLocal()
    try:
        run_sf_nightly_auto_push_for_all_stores(db)
    finally:
        db.close()


def add_cron_jobs(sched) -> None:
    """向任意 APScheduler 实例注册全部 cron 任务（API 内嵌或独立 worker 共用）。"""
    sched.add_job(job_reset_leave_flags, "cron", hour=0, minute=1, id="reset_leave", replace_existing=True)
    sched.add_job(job_low_balance_notify, "cron", hour=17, minute=0, id="low_balance", replace_existing=True)
    sched.add_job(
        job_sf_nightly_auto_push,
        "cron",
        hour=8,
        minute=50,
        id="sf_nightly_push",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        job_expire_unpaid_single_meal_orders,
        "interval",
        minutes=2,
        id="expire_unpaid_single_meals",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        job_expire_stale_unpaid_miniprogram_card_orders,
        "interval",
        minutes=2,
        id="expire_stale_unpaid_card_coupons",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        job_expire_unpaid_store_retail_orders,
        "interval",
        minutes=2,
        id="expire_unpaid_store_retail_orders",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def setup_scheduler() -> None:
    if not settings.ENABLE_IN_PROCESS_SCHEDULER:
        logger.info(
            "进程内调度器未启用（ENABLE_IN_PROCESS_SCHEDULER=false）；"
            "定时任务请使用独立 worker：python -m app.jobs.worker"
        )
        return
    if scheduler.running:
        return
    add_cron_jobs(scheduler)
    scheduler.start()
    logger.info("进程内 APScheduler 已启动（仅建议在本地开发使用）")


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
