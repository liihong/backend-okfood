"""临时脚本：统计 daily single-meals 列表+summary 的 SQL 次数与耗时。"""
from __future__ import annotations

import time
from datetime import date

from sqlalchemy import event

from app.db.session import SessionLocal
from app.services.single_meal_order_service import (
    list_admin_store_single_meal_orders_by_delivery_day,
    summarize_admin_store_single_meal_orders_by_delivery_day,
)


def main() -> None:
    day = date(2026, 6, 29)
    store_id = 1
    queries: list[str] = []

    db = SessionLocal()
    try:
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            queries.append(str(statement)[:160])

        event.listen(db.get_bind(), "before_cursor_execute", before_cursor_execute)

        t0 = time.perf_counter()
        items, total = list_admin_store_single_meal_orders_by_delivery_day(
            db,
            store_id=store_id,
            delivery_day=day,
            page=1,
            page_size=20,
        )
        t1 = time.perf_counter()
        q_list = len(queries)
        print(f"list only: {len(items)} items, total={total}, {t1 - t0:.3f}s, queries={q_list}")

        queries.clear()
        t2 = time.perf_counter()
        summary = summarize_admin_store_single_meal_orders_by_delivery_day(
            db,
            store_id=store_id,
            delivery_day=day,
        )
        t3 = time.perf_counter()
        print(f"summary only: {t3 - t2:.3f}s, queries={len(queries)}, data={summary}")
        print(f"full page load (list+summary): {t3 - t0:.3f}s, queries={q_list + len(queries)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
