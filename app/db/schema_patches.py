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


def apply_member_addresses_pca_columns() -> None:
    """为 member_addresses 增加 province / city / district；已存在则跳过。"""
    try:
        insp = inspect(engine)
        if not insp.has_table("member_addresses"):
            return
        col_names = {c["name"].lower() for c in insp.get_columns("member_addresses")}
    except Exception as e:
        logger.warning("补库: 无法检查 member_addresses 表结构: %s", e)
        return

    if "province" in col_names and "city" in col_names and "district" in col_names:
        return

    dname = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dname in ("mysql", "mariadb"):
                if "province" not in col_names:
                    conn.execute(
                        text(
                            "ALTER TABLE `member_addresses` ADD COLUMN `province` VARCHAR(64) NULL "
                            "COMMENT '省' AFTER `lat`"
                        )
                    )
                if "city" not in col_names:
                    conn.execute(
                        text(
                            "ALTER TABLE `member_addresses` ADD COLUMN `city` VARCHAR(64) NULL "
                            "COMMENT '市' AFTER `province`"
                        )
                    )
                if "district" not in col_names:
                    conn.execute(
                        text(
                            "ALTER TABLE `member_addresses` ADD COLUMN `district` VARCHAR(64) NULL "
                            "COMMENT '区' AFTER `city`"
                        )
                    )
            elif dname == "sqlite":
                if "province" not in col_names:
                    conn.execute(text("ALTER TABLE member_addresses ADD COLUMN province VARCHAR(64)"))
                if "city" not in col_names:
                    conn.execute(text("ALTER TABLE member_addresses ADD COLUMN city VARCHAR(64)"))
                if "district" not in col_names:
                    conn.execute(text("ALTER TABLE member_addresses ADD COLUMN district VARCHAR(64)"))
            else:
                logger.error(
                    "补库: 当前库类型 %s 需手动执行 "
                    "sql/migrations/20260429_member_addresses_pca.sql",
                    dname,
                )
                return
        logger.info("补库: 已添加 member_addresses.province / city / district")
    except Exception as e:
        logger.error(
            "补库: 添加 province/city/district 失败，请手动执行 "
            "sql/migrations/20260429_member_addresses_pca.sql: %s",
            e,
        )


def apply_sf_same_city_callback_support() -> None:
    """顺丰回调表及对 sf_same_city_pushes 的增量列；未迁移时补齐。"""
    try:
        insp = inspect(engine)
        dname = engine.dialect.name
    except Exception as e:
        logger.warning("补库: 无法连接数据库检查顺丰回调: %s", e)
        return

    if dname not in ("mysql", "mariadb", "sqlite"):
        logger.warning(
            "补库: 顺丰回调需手动执行 sql/migrations/20260428_sf_same_city_callbacks.sql，当前 dialect=%s",
            dname,
        )
        return

    try:
        insp = inspect(engine)
        callbacks_exists = insp.has_table("sf_same_city_callbacks")
        pushes_exists = insp.has_table("sf_same_city_pushes")

        cols_push: set[str] = set()
        if pushes_exists:
            cols_push = {c["name"].lower() for c in insp.get_columns("sf_same_city_pushes")}

        with engine.begin() as conn:
            if not callbacks_exists:
                if dname in ("mysql", "mariadb"):
                    conn.execute(
                        text(
                            """
CREATE TABLE IF NOT EXISTS `sf_same_city_callbacks` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `route_kind` VARCHAR(64) NOT NULL,
  `sign_ok` TINYINT(1) NOT NULL DEFAULT 0,
  `error_message` VARCHAR(512) NULL DEFAULT NULL,
  `shop_order_id` VARCHAR(128) NULL DEFAULT NULL,
  `sf_order_id` VARCHAR(64) NULL DEFAULT NULL,
  `payload_json` JSON NULL,
  `raw_body` MEDIUMTEXT NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_sf_cb_shop_order` (`shop_order_id`),
  KEY `idx_sf_cb_sf_order` (`sf_order_id`),
  KEY `idx_sf_cb_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                            """.strip()
                        )
                    )
                else:
                    conn.execute(
                        text(
                            """
CREATE TABLE IF NOT EXISTS sf_same_city_callbacks (
  id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  route_kind VARCHAR(64) NOT NULL,
  sign_ok INTEGER NOT NULL DEFAULT 0,
  error_message VARCHAR(512),
  shop_order_id VARCHAR(128),
  sf_order_id VARCHAR(64),
  payload_json TEXT,
  raw_body TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
                            """.strip()
                        )
                    )

            if pushes_exists and "last_callback_at" not in cols_push:
                if dname in ("mysql", "mariadb"):
                    conn.execute(
                        text(
                            """
ALTER TABLE `sf_same_city_pushes`
 ADD COLUMN `last_callback_at` DATETIME NULL DEFAULT NULL AFTER `created_at`,
 ADD COLUMN `last_callback_kind` VARCHAR(64) NULL DEFAULT NULL AFTER `last_callback_at`,
 ADD COLUMN `sf_callback_order_status` INT NULL DEFAULT NULL AFTER `last_callback_kind`
                            """.strip()
                        )
                    )
                elif dname == "sqlite":
                    conn.execute(text("ALTER TABLE sf_same_city_pushes ADD COLUMN last_callback_at TIMESTAMP"))
                    conn.execute(text("ALTER TABLE sf_same_city_pushes ADD COLUMN last_callback_kind VARCHAR(64)"))
                    conn.execute(
                        text(
                            "ALTER TABLE sf_same_city_pushes ADD COLUMN sf_callback_order_status INTEGER"
                        )
                    )

        logger.info("补库: 已检查顺丰推送回调表 / sf_same_city_pushes 顺丰状态列")
    except Exception as e:
        logger.warning("补库: 顺丰回调表补齐失败（可手动执行 sql/migrations/20260428）：%s", e)
