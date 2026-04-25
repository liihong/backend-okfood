"""
启动时轻量补库：与 sql/migrations 中手动脚本保持一致，避免未跑迁移时 ORM 读写失败。
"""

import logging

from sqlalchemy import inspect, text

from app.db.session import engine

logger = logging.getLogger(__name__)


def apply_members_tomorrow_leave_target_column() -> None:
    """为 members 增加 tomorrow_leave_target_date；已存在则跳过。"""
    try:
        insp = inspect(engine)
        if not insp.has_table("members"):
            return
        col_names = {c["name"].lower() for c in insp.get_columns("members")}
    except Exception as e:
        logger.warning("补库: 无法检查 members 表结构: %s", e)
        return

    if "tomorrow_leave_target_date" in col_names:
        return

    dname = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dname in ("mysql", "mariadb"):
                conn.execute(
                    text(
                        "ALTER TABLE `members` ADD COLUMN `tomorrow_leave_target_date` DATE NULL "
                        "COMMENT '仅明日请假：不配送目标业务日（上海）' "
                        "AFTER `is_leaved_tomorrow`"
                    )
                )
            elif dname == "sqlite":
                conn.execute(
                    text(
                        "ALTER TABLE members ADD COLUMN tomorrow_leave_target_date DATE"
                    )
                )
            else:
                logger.error(
                    "补库: 当前库类型 %s 需手动执行 "
                    "sql/migrations/20260425_members_tomorrow_leave_target_date.sql",
                    dname,
                )
                return
        logger.info("补库: 已添加 members.tomorrow_leave_target_date")
    except Exception as e:
        logger.error(
            "补库: 添加 tomorrow_leave_target_date 失败，请手动执行 "
            "sql/migrations/20260425_members_tomorrow_leave_target_date.sql: %s",
            e,
        )


def apply_member_addresses_map_door_columns() -> None:
    """为 member_addresses 增加 map_location_text、door_detail；已存在则跳过。"""
    try:
        insp = inspect(engine)
        if not insp.has_table("member_addresses"):
            return
        col_names = {c["name"].lower() for c in insp.get_columns("member_addresses")}
    except Exception as e:
        logger.warning("补库: 无法检查 member_addresses 表结构: %s", e)
        return

    if "map_location_text" in col_names and "door_detail" in col_names:
        return

    dname = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dname in ("mysql", "mariadb"):
                if "map_location_text" not in col_names:
                    conn.execute(
                        text(
                            "ALTER TABLE `member_addresses` "
                            "ADD COLUMN `map_location_text` VARCHAR(500) NULL "
                            "COMMENT '地图选点/省市区道路小区等收货位置文字' "
                            "AFTER `detail_address`"
                        )
                    )
                if "door_detail" not in col_names:
                    conn.execute(
                        text(
                            "ALTER TABLE `member_addresses` "
                            "ADD COLUMN `door_detail` VARCHAR(500) NULL "
                            "COMMENT '楼栋、单元、门牌等补充地址' "
                            "AFTER `map_location_text`"
                        )
                    )
            elif dname == "sqlite":
                if "map_location_text" not in col_names:
                    conn.execute(
                        text("ALTER TABLE member_addresses ADD COLUMN map_location_text VARCHAR(500)")
                    )
                if "door_detail" not in col_names:
                    conn.execute(
                        text("ALTER TABLE member_addresses ADD COLUMN door_detail VARCHAR(500)")
                    )
            else:
                logger.error(
                    "补库: 当前库类型 %s 需手动执行 "
                    "sql/migrations/20260427_member_addresses_map_door.sql",
                    dname,
                )
                return
        logger.info("补库: 已添加 member_addresses.map_location_text / door_detail")
    except Exception as e:
        logger.error(
            "补库: 添加 map_location_text / door_detail 失败，请手动执行 "
            "sql/migrations/20260427_member_addresses_map_door.sql: %s",
            e,
        )
