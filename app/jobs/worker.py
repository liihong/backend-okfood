"""独立定时任务进程：与 uvicorn API 分离，避免 08:50 推单占满 API worker。

启动::

    python -m app.jobs.worker

生产 systemd 示例见 ``deploy/okfine-scheduler.service.example``。
"""

from __future__ import annotations

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

from app.jobs.scheduler import add_cron_jobs

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    sched = BlockingScheduler(timezone="Asia/Shanghai")
    add_cron_jobs(sched)

    def _stop(*_args: object) -> None:
        logger.info("Scheduler worker 收到停止信号，正在退出…")
        sched.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logger.info("Okfood scheduler worker 已启动（BlockingScheduler / Asia/Shanghai）")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler worker 已停止")


if __name__ == "__main__":
    main()
