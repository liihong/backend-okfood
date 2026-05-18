"""
启动时轻量补库：与 sql/migrations 中手动脚本保持一致，避免未跑迁移时 ORM 读写失败。
"""

import logging

from sqlalchemy import inspect, text

from app.db.session import engine

logger = logging.getLogger(__name__)


def apply_members_skip_subscription_saturday_column() -> None:
    """为 members 增加 skip_subscription_saturday；已存在则跳过。"""
    try:
        insp = inspect(engine)
        if not insp.has_table("members"):
            return
        col_names = {c["name"].lower() for c in insp.get_columns("members")}
    except Exception as e:
        logger.warning("补库: 无法检查 members 表结构: %s", e)
        return

    if "skip_subscription_saturday" in col_names:
        return

    dname = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dname in ("mysql", "mariadb"):
                conn.execute(
                    text(
                        "ALTER TABLE `members` ADD COLUMN `skip_subscription_saturday` TINYINT(1) NOT NULL DEFAULT 0 "
                        "COMMENT '固定周六不参与订阅履约（全局日历仍为履约日时生效）' AFTER `store_pickup`"
                    )
                )
            elif dname == "sqlite":
                conn.execute(
                    text(
                        "ALTER TABLE members ADD COLUMN skip_subscription_saturday INTEGER NOT NULL DEFAULT 0"
                    )
                )
            else:
                logger.error(
                    "补库: 当前库类型 %s 需手动执行 "
                    "sql/migrations/20260506_members_skip_subscription_saturday.sql",
                    dname,
                )
                return
        logger.info("补库: 已添加 members.skip_subscription_saturday")
    except Exception as e:
        logger.error(
            "补库: 添加 skip_subscription_saturday 失败，请手动执行 "
            "sql/migrations/20260506_members_skip_subscription_saturday.sql: %s",
            e,
        )


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
    after_first = "detail_address" if "detail_address" in col_names else "delivery_region_id"
    try:
        with engine.begin() as conn:
            if dname in ("mysql", "mariadb"):
                if "map_location_text" not in col_names:
                    conn.execute(
                        text(
                            "ALTER TABLE `member_addresses` "
                            "ADD COLUMN `map_location_text` VARCHAR(500) NULL "
                            "COMMENT '地图选点/收货位置主文案' "
                            f"AFTER `{after_first}`"
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


def apply_member_addresses_drop_legacy_columns() -> None:
    """
    移除 member_addresses 的 detail_address 与省市区独立列；数据并入 map_location_text / door_detail。
    须在 map_location_text、door_detail 列已存在后执行（见 apply_member_addresses_map_door_columns）。
    """
    try:
        insp = inspect(engine)
        if not insp.has_table("member_addresses"):
            return
        col_names = {c["name"].lower() for c in insp.get_columns("member_addresses")}
    except Exception as e:
        logger.warning("补库: 无法检查 member_addresses 表结构: %s", e)
        return

    legacy = [c for c in ("province", "city", "district", "detail_address") if c in col_names]
    if not legacy:
        return
    if "map_location_text" not in col_names:
        logger.warning("补库: member_addresses 尚无 map_location_text，跳过删省市区/detail_address（请先补 map/door 列）")
        return

    dname = engine.dialect.name
    if dname not in ("mysql", "mariadb", "sqlite"):
        logger.warning(
            "补库: member_addresses 删列需手动执行 sql/migrations/20260506_member_addresses_drop_detail_pca.sql，"
            "当前 dialect=%s",
            dname,
        )
        return

    try:
        with engine.begin() as conn:
            if "detail_address" in col_names:
                if dname in ("mysql", "mariadb"):
                    conn.execute(
                        text(
                            "UPDATE `member_addresses` SET `map_location_text` = TRIM(`detail_address`) "
                            "WHERE (`map_location_text` IS NULL OR TRIM(`map_location_text`) = '') "
                            "AND `detail_address` IS NOT NULL AND TRIM(`detail_address`) <> ''"
                        )
                    )
                elif dname == "sqlite":
                    conn.execute(
                        text(
                            "UPDATE member_addresses SET map_location_text = TRIM(detail_address) "
                            "WHERE (map_location_text IS NULL OR TRIM(map_location_text) = '') "
                            "AND detail_address IS NOT NULL AND TRIM(detail_address) <> ''"
                        )
                    )

            drops = [c for c in ("province", "city", "district", "detail_address") if c in col_names]
            for col in drops:
                if dname in ("mysql", "mariadb"):
                    conn.execute(text(f"ALTER TABLE `member_addresses` DROP COLUMN `{col}`"))
                elif dname == "sqlite":
                    conn.execute(text(f"ALTER TABLE member_addresses DROP COLUMN {col}"))

        logger.info("补库: 已移除 member_addresses 的 detail_address / province / city / district（如曾存在）")
    except Exception as e:
        logger.error(
            "补库: 移除 member_addresses 旧列失败，请手动执行 "
            "sql/migrations/20260506_member_addresses_drop_detail_pca.sql: %s",
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

            if pushes_exists:
                insp_fresh = inspect(engine)
                cols_after = {c["name"].lower() for c in insp_fresh.get_columns("sf_same_city_pushes")}
                if "store_id" not in cols_after:
                    if dname in ("mysql", "mariadb"):
                        conn.execute(
                            text(
                                "ALTER TABLE `sf_same_city_pushes` "
                                "ADD COLUMN `store_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`"
                            )
                        )
                    elif dname == "sqlite":
                        conn.execute(
                            text("ALTER TABLE sf_same_city_pushes ADD COLUMN store_id INTEGER NOT NULL DEFAULT 1")
                        )

        logger.info("补库: 已检查顺丰推送回调表 / sf_same_city_pushes 顺丰状态列")
    except Exception as e:
        logger.warning("补库: 顺丰回调表补齐失败（可手动执行 sql/migrations/20260428）：%s", e)


def apply_admin_dashboard_biz_day_snapshot_expire_one_unit_column() -> None:
    """为 admin_dashboard_biz_day_snapshots 增加 today_expire_one_unit_members；已存在则跳过。"""
    try:
        insp = inspect(engine)
        if not insp.has_table("admin_dashboard_biz_day_snapshots"):
            return
        col_names = {c["name"].lower() for c in insp.get_columns("admin_dashboard_biz_day_snapshots")}
    except Exception as e:
        logger.warning("补库: 无法检查 admin_dashboard_biz_day_snapshots 表结构: %s", e)
        return

    if "today_expire_one_unit_members" in col_names:
        return

    dname = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dname in ("mysql", "mariadb"):
                conn.execute(
                    text(
                        "ALTER TABLE `admin_dashboard_biz_day_snapshots` "
                        "ADD COLUMN `today_expire_one_unit_members` INT NOT NULL DEFAULT 0 "
                        "COMMENT '锚定日应履约且 balance 恰等于每配送日份数（仅剩 1 次）的会员数' "
                        "AFTER `tomorrow_meals_to_prepare`"
                    )
                )
            elif dname == "sqlite":
                conn.execute(
                    text(
                        "ALTER TABLE admin_dashboard_biz_day_snapshots "
                        "ADD COLUMN today_expire_one_unit_members INTEGER NOT NULL DEFAULT 0"
                    )
                )
            else:
                logger.error(
                    "补库: 当前库类型 %s 需手动执行 sql/migrations/20260508_admin_dashboard_expire_one_unit.sql",
                    dname,
                )
                return
        logger.info("补库: 已添加 admin_dashboard_biz_day_snapshots.today_expire_one_unit_members")
    except Exception as e:
        logger.error(
            "补库: 添加 today_expire_one_unit_members 失败，请手动执行 "
            "sql/migrations/20260508_admin_dashboard_expire_one_unit.sql: %s",
            e,
        )


def apply_drop_menu_dish_month_unique_constraints() -> None:
    """移除菜单「同月同一道菜仅出现一次」唯一索引；已不存在则跳过。"""
    try:
        insp = inspect(engine)
        if not insp.has_table("weekly_menu_slot") or not insp.has_table("menu_schedule"):
            return
    except Exception as e:
        logger.warning("补库: 无法检查菜单表: %s", e)
        return

    dname = engine.dialect.name
    if dname not in ("mysql", "mariadb"):
        return

    def index_exists(conn, table: str, name: str) -> bool:
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND table_name = :t AND index_name = :n LIMIT 1"
            ),
            {"t": table, "n": name},
        )
        return r.scalar() is not None

    try:
        with engine.begin() as conn:
            if index_exists(conn, "weekly_menu_slot", "uk_weekly_dish_month"):
                conn.execute(text("ALTER TABLE `weekly_menu_slot` DROP INDEX `uk_weekly_dish_month`"))
                logger.info("补库: 已移除 weekly_menu_slot.uk_weekly_dish_month")
            if index_exists(conn, "menu_schedule", "uk_schedule_dish_month"):
                conn.execute(text("ALTER TABLE `menu_schedule` DROP INDEX `uk_schedule_dish_month`"))
                logger.info("补库: 已移除 menu_schedule.uk_schedule_dish_month")
    except Exception as e:
        logger.error(
            "补库: 移除菜单月去重索引失败，请手动执行 "
            "sql/migrations/20260511_drop_menu_dish_month_unique.sql: %s",
            e,
        )


def apply_menu_dish_spice_internal_sop_columns() -> None:
    """menu_dish：辣度与内部 SOP 文本；未迁移时补齐。"""
    try:
        insp = inspect(engine)
        if not insp.has_table("menu_dish"):
            return
        col_names = {c["name"].lower() for c in insp.get_columns("menu_dish")}
    except Exception as e:
        logger.warning("补库: 无法检查 menu_dish 表结构: %s", e)
        return

    if "spice_level" in col_names and "internal_view_sop" in col_names:
        return

    dname = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dname in ("mysql", "mariadb"):
                if "spice_level" not in col_names:
                    conn.execute(
                        text(
                            "ALTER TABLE `menu_dish` ADD COLUMN `spice_level` VARCHAR(16) NULL DEFAULT NULL "
                            "COMMENT '辣度代码：none/mild/medium/hot' AFTER `single_order_price_yuan`"
                        )
                    )
                if "internal_view_sop" not in col_names:
                    conn.execute(
                        text(
                            "ALTER TABLE `menu_dish` ADD COLUMN `internal_view_sop` TEXT NULL "
                            "COMMENT '内部查看操作说明，不对会员展示' AFTER `spice_level`"
                        )
                    )
            elif dname == "sqlite":
                if "spice_level" not in col_names:
                    conn.execute(text("ALTER TABLE menu_dish ADD COLUMN spice_level VARCHAR(16)"))
                if "internal_view_sop" not in col_names:
                    conn.execute(text("ALTER TABLE menu_dish ADD COLUMN internal_view_sop TEXT"))
            else:
                logger.error(
                    "补库: 当前库类型 %s 需手动执行 sql/migrations/20260511_menu_dish_spice_internal_sop.sql",
                    dname,
                )
                return
        logger.info("补库: 已添加 menu_dish.spice_level / internal_view_sop")
    except Exception as e:
        logger.error(
            "补库: 添加 menu_dish 辣度/SOP 列失败，请手动执行 "
            "sql/migrations/20260511_menu_dish_spice_internal_sop.sql: %s",
            e,
        )


def apply_tenant_integration_settings_table() -> None:
    """租户对接配置表（小程序 / 微信商户 / 顺丰等）；未迁移时启动创建。"""
    try:
        insp = inspect(engine)
        if not insp.has_table("tenants"):
            return
        if insp.has_table("tenant_integration_settings"):
            return
    except Exception as e:
        logger.warning("补库: 无法检查 tenant_integration_settings: %s", e)
        return

    dname = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dname in ("mysql", "mariadb"):
                conn.execute(
                    text(
                        """
CREATE TABLE IF NOT EXISTS `tenant_integration_settings` (
  `tenant_id` INT UNSIGNED NOT NULL,
  `wx_mini_appid` VARCHAR(64) NULL,
  `wx_mini_secret` VARCHAR(128) NULL,
  `wechat_pay_mch_id` VARCHAR(32) NULL,
  `wechat_pay_api_key` VARCHAR(128) NULL,
  `wechat_pay_notify_url` VARCHAR(512) NULL,
  `wx_subscribe_delivery_tmpl_id` VARCHAR(128) NULL,
  `sf_open_dev_id` INT NULL,
  `sf_open_secret` VARCHAR(255) NULL,
  `sf_open_shop_id` VARCHAR(64) NULL,
  `sf_open_shop_type` INT NULL,
  `sf_pickup_phone` VARCHAR(32) NULL,
  `sf_pickup_address` VARCHAR(512) NULL,
  `sf_city_name` VARCHAR(64) NULL,
  `extra_json` TEXT NULL,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`tenant_id`),
  CONSTRAINT `fk_tis_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                        """
                    )
                )
            elif dname == "sqlite":
                conn.execute(
                    text(
                        """
CREATE TABLE IF NOT EXISTS tenant_integration_settings (
  tenant_id INTEGER NOT NULL PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
  wx_mini_appid VARCHAR(64),
  wx_mini_secret VARCHAR(128),
  wechat_pay_mch_id VARCHAR(32),
  wechat_pay_api_key VARCHAR(128),
  wechat_pay_notify_url VARCHAR(512),
  wx_subscribe_delivery_tmpl_id VARCHAR(128),
  sf_open_dev_id INTEGER,
  sf_open_secret VARCHAR(255),
  sf_open_shop_id VARCHAR(64),
  sf_open_shop_type INTEGER,
  sf_pickup_phone VARCHAR(32),
  sf_pickup_address VARCHAR(512),
  sf_city_name VARCHAR(64),
  extra_json TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
                        """
                    )
                )
            else:
                logger.error(
                    "补库: 当前库类型 %s 无法自动创建 tenant_integration_settings，请手动执行迁移",
                    dname,
                )
                return
        logger.info("补库: 已创建 tenant_integration_settings")
    except Exception as e:
        logger.error("补库: tenant_integration_settings 创建失败: %s", e)


def apply_member_card_orders_membership_template_id_column() -> None:
    """member_card_orders 增加 membership_template_id（自律卡包下单）。"""
    try:
        insp = inspect(engine)
        if not insp.has_table("member_card_orders"):
            return
        col_names = {c["name"].lower() for c in insp.get_columns("member_card_orders")}
    except Exception as e:
        logger.warning("补库: 无法检查 member_card_orders 表结构: %s", e)
        return

    if "membership_template_id" in col_names:
        return

    dname = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dname in ("mysql", "mariadb"):
                conn.execute(
                    text(
                        "ALTER TABLE `member_card_orders` ADD COLUMN `membership_template_id` BIGINT UNSIGNED NULL "
                        "DEFAULT NULL COMMENT '会员卡模版 id' AFTER `member_id`"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE `member_card_orders` ADD KEY `idx_mco_membership_template` (`membership_template_id`)"
                    )
                )
                conn.execute(
                    text(
                        "ALTER TABLE `member_card_orders` ADD CONSTRAINT `fk_mco_membership_template` "
                        "FOREIGN KEY (`membership_template_id`) REFERENCES `membership_card_templates` (`id`) "
                        "ON UPDATE CASCADE ON DELETE SET NULL"
                    )
                )
            elif dname == "sqlite":
                conn.execute(text("ALTER TABLE member_card_orders ADD COLUMN membership_template_id INTEGER"))
            else:
                logger.error(
                    "补库: 当前库类型 %s 需手动执行 "
                    "sql/migrations/20260518_member_card_orders_membership_template_id.sql",
                    dname,
                )
                return
        logger.info("补库: 已添加 member_card_orders.membership_template_id")
    except Exception as e:
        logger.error(
            "补库: 添加 membership_template_id 失败，请手动执行 "
            "sql/migrations/20260518_member_card_orders_membership_template_id.sql: %s",
            e,
        )
