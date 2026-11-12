"""存量库幂等补丁：启动时补列，避免新代码读到旧表结构。"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_USAGE_INDEX = "idx_member_addresses_member_usage_default"


def ensure_member_address_usage_schema(engine: Engine) -> None:
    """为 member_addresses 补 address_usage 列（meal/retail），已存在则跳过。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "member_addresses" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("member_addresses")}
    dialect = engine.dialect.name
    if "address_usage" not in cols:
        with engine.begin() as conn:
            if dialect == "sqlite":
                conn.execute(
                    text(
                        "ALTER TABLE member_addresses "
                        "ADD COLUMN address_usage VARCHAR(16) NOT NULL DEFAULT 'meal'"
                    )
                )
            else:
                conn.execute(
                    text(
                        "ALTER TABLE `member_addresses` "
                        "ADD COLUMN `address_usage` VARCHAR(16) NOT NULL DEFAULT 'meal' "
                        "COMMENT 'meal=会员送餐地址；retail=果蔬汁/月饼等商城收货地址' "
                        "AFTER `is_default`"
                    )
                )
        logger.info("已为 member_addresses 补 address_usage 列")

    if dialect == "sqlite":
        return
    insp = inspect(engine)
    idx_names = {i["name"] for i in insp.get_indexes("member_addresses")}
    if _USAGE_INDEX in idx_names:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE `member_addresses` "
                f"ADD INDEX `{_USAGE_INDEX}` "
                "(`member_id`, `address_usage`, `is_default`)"
            )
        )
    logger.info("已为 member_addresses 补 address_usage 索引")


def ensure_store_sf_merge_same_address_push_schema(engine: Engine) -> None:
    """为 stores 补同址合并推顺丰开关列，已存在则跳过。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "stores" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("stores")}
    if "sf_merge_same_address_push" in cols:
        return
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(
                text(
                    "ALTER TABLE stores "
                    "ADD COLUMN sf_merge_same_address_push BOOLEAN NOT NULL DEFAULT 0"
                )
            )
        else:
            after = ""
            if "sf_nightly_auto_push_enabled" in cols:
                after = " AFTER `sf_nightly_auto_push_enabled`"
            conn.execute(
                text(
                    "ALTER TABLE `stores` "
                    "ADD COLUMN `sf_merge_same_address_push` TINYINT(1) NOT NULL DEFAULT 0 "
                    "COMMENT '同地址不同会员是否合并为一单推顺丰；0=按会员拆分（默认）'"
                    f"{after}"
                )
            )
    logger.info("已为 stores 补 sf_merge_same_address_push 列")


def ensure_members_pause_effective_date_schema(engine: Engine) -> None:
    """为 members 补小程序暂停生效日列，已存在则跳过。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "members" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("members")}
    if "pause_effective_date" in cols:
        return
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(text("ALTER TABLE members ADD COLUMN pause_effective_date DATE"))
        else:
            after = ""
            if "delivery_deferred" in cols:
                after = " AFTER `delivery_deferred`"
            conn.execute(
                text(
                    "ALTER TABLE `members` "
                    "ADD COLUMN `pause_effective_date` DATE NULL "
                    "COMMENT '小程序自助暂停生效业务日；有值且<=履约日则不进大表，当天仍配送'"
                    f"{after}"
                )
            )
    logger.info("已为 members 补 pause_effective_date 列")


def ensure_dinner_gift_schema(engine: Engine) -> None:
    """补晚餐暂停/指定配送日，以及会员卡赠送晚餐、赠送果蔬汁列。已存在则跳过。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if "member_meal_period_state" in tables:
            cols = {c["name"] for c in insp.get_columns("member_meal_period_state")}
            if "dinner_delivery_paused" not in cols:
                if dialect == "sqlite":
                    conn.execute(
                        text(
                            "ALTER TABLE member_meal_period_state "
                            "ADD COLUMN dinner_delivery_paused BOOLEAN NOT NULL DEFAULT 0"
                        )
                    )
                else:
                    conn.execute(
                        text(
                            "ALTER TABLE `member_meal_period_state` "
                            "ADD COLUMN `dinner_delivery_paused` TINYINT(1) NOT NULL DEFAULT 0 "
                            "COMMENT '只暂停晚餐日程，不影响午餐'"
                        )
                    )
            if "dinner_deliver_on" not in cols:
                if dialect == "sqlite":
                    conn.execute(
                        text("ALTER TABLE member_meal_period_state ADD COLUMN dinner_deliver_on DATE")
                    )
                else:
                    conn.execute(
                        text(
                            "ALTER TABLE `member_meal_period_state` "
                            "ADD COLUMN `dinner_deliver_on` DATE NULL "
                            "COMMENT '晚餐指定配送日；暂停时只在这一天进晚餐单'"
                        )
                    )
        if "membership_card_templates" in tables:
            cols = {c["name"] for c in insp.get_columns("membership_card_templates")}
            if "gift_dinner_meals" not in cols:
                ddl = (
                    "ALTER TABLE membership_card_templates ADD COLUMN gift_dinner_meals INTEGER NOT NULL DEFAULT 0"
                    if dialect == "sqlite"
                    else "ALTER TABLE `membership_card_templates` ADD COLUMN `gift_dinner_meals` INT NOT NULL DEFAULT 0 "
                    "COMMENT '赠送晚餐次数，不写入餐段快照'"
                )
                conn.execute(text(ddl))
            if "gift_retail_product_id" not in cols:
                ddl = (
                    "ALTER TABLE membership_card_templates ADD COLUMN gift_retail_product_id BIGINT"
                    if dialect == "sqlite"
                    else "ALTER TABLE `membership_card_templates` ADD COLUMN `gift_retail_product_id` BIGINT NULL "
                    "COMMENT '赠送果蔬汁 SKU'"
                )
                conn.execute(text(ddl))
            if "gift_retail_quantity" not in cols:
                ddl = (
                    "ALTER TABLE membership_card_templates ADD COLUMN gift_retail_quantity INTEGER NOT NULL DEFAULT 0"
                    if dialect == "sqlite"
                    else "ALTER TABLE `membership_card_templates` ADD COLUMN `gift_retail_quantity` INT NOT NULL DEFAULT 0 "
                    "COMMENT '赠送果蔬汁单数，开卡时逐笔建单'"
                )
                conn.execute(text(ddl))
    logger.info("已检查晚餐暂停与开卡赠送列")


def ensure_menu_drink_schema(engine: Engine) -> None:
    """随餐饮饮品表，以及菜品上的配餐饮列。已存在则跳过。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    dialect = engine.dialect.name
    if "menu_drink" not in tables:
        with engine.begin() as conn:
            if dialect == "sqlite":
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS menu_drink ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "store_id BIGINT NOT NULL, "
                        "name VARCHAR(200) NOT NULL, "
                        "description VARCHAR(1000), "
                        "image_url TEXT, "
                        "is_enabled BOOLEAN NOT NULL DEFAULT 1, "
                        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
                        ")"
                    )
                )
            else:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS `menu_drink` ("
                        "`id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, "
                        "`store_id` BIGINT UNSIGNED NOT NULL, "
                        "`name` VARCHAR(200) NOT NULL COMMENT '饮品名称', "
                        "`description` VARCHAR(1000) NULL COMMENT '随餐说明', "
                        "`image_url` TEXT NULL, "
                        "`is_enabled` TINYINT(1) NOT NULL DEFAULT 1, "
                        "`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                        "`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, "
                        "PRIMARY KEY (`id`), "
                        "KEY `idx_menu_drink_store` (`store_id`), "
                        "CONSTRAINT `fk_menu_drink_store` FOREIGN KEY (`store_id`) "
                        "REFERENCES `stores` (`id`) ON UPDATE CASCADE"
                        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci "
                        "COMMENT='随餐饮饮品，供菜品配餐饮选用'"
                    )
                )
        logger.info("已创建 menu_drink")

    insp = inspect(engine)
    if "menu_dish" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("menu_dish")}
    if "paired_drink_id" in cols:
        return
    with engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(text("ALTER TABLE menu_dish ADD COLUMN paired_drink_id BIGINT"))
        else:
            after = " AFTER `dish_type_category_id`" if "dish_type_category_id" in cols else ""
            conn.execute(
                text(
                    "ALTER TABLE `menu_dish` "
                    "ADD COLUMN `paired_drink_id` BIGINT NULL "
                    "COMMENT '配餐饮，menu_drink.id，可空'"
                    f"{after}"
                )
            )
    logger.info("已为 menu_dish 补 paired_drink_id 列")


def ensure_prep_menu_schema(engine: Engine) -> None:
    """开菜单食材与菜品配菜行。表已存在则跳过，不改旧表。"""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if "prep_ingredient" not in tables:
            if dialect == "sqlite":
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS prep_ingredient ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "store_id BIGINT NOT NULL, "
                        "name VARCHAR(64) NOT NULL, "
                        "unit VARCHAR(16) NOT NULL, "
                        "yield_rate NUMERIC(6, 4) NOT NULL DEFAULT 1, "
                        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                        "UNIQUE (store_id, name), "
                        "CHECK (unit IN ('g', 'piece')), "
                        "CHECK (yield_rate > 0 AND yield_rate <= 1)"
                        ")"
                    )
                )
            else:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS `prep_ingredient` ("
                        "`id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, "
                        "`store_id` BIGINT UNSIGNED NOT NULL, "
                        "`name` VARCHAR(64) NOT NULL COMMENT '食材名称，同一门店唯一', "
                        "`unit` VARCHAR(16) NOT NULL COMMENT 'g=克；piece=个', "
                        "`yield_rate` DECIMAL(6, 4) NOT NULL DEFAULT 1.0000 "
                        "COMMENT '净菜/毛菜，大于 0 且不超过 1；按个计固定为 1', "
                        "`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                        "`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, "
                        "PRIMARY KEY (`id`), "
                        "UNIQUE KEY `uk_prep_ingredient_store_name` (`store_id`, `name`), "
                        "KEY `idx_prep_ingredient_store` (`store_id`), "
                        "CONSTRAINT `fk_prep_ingredient_store` FOREIGN KEY (`store_id`) "
                        "REFERENCES `stores` (`id`) ON UPDATE CASCADE, "
                        "CONSTRAINT `chk_prep_ingredient_unit` CHECK (`unit` IN ('g', 'piece')), "
                        "CONSTRAINT `chk_prep_ingredient_yield` CHECK (`yield_rate` > 0 AND `yield_rate` <= 1)"
                        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci "
                        "COMMENT='开菜单食材与出成率'"
                    )
                )
            logger.info("已创建 prep_ingredient")
        if "dish_prep_sop_line" not in tables:
            if dialect == "sqlite":
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS dish_prep_sop_line ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "store_id BIGINT NOT NULL, "
                        "dish_id BIGINT NOT NULL, "
                        "ingredient_id BIGINT NOT NULL, "
                        "gross_qty_per_portion NUMERIC(12, 3) NOT NULL, "
                        "sort_order INTEGER NOT NULL DEFAULT 0, "
                        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                        "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                        "UNIQUE (dish_id, ingredient_id), "
                        "CHECK (gross_qty_per_portion > 0)"
                        ")"
                    )
                )
            else:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS `dish_prep_sop_line` ("
                        "`id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, "
                        "`store_id` BIGINT UNSIGNED NOT NULL, "
                        "`dish_id` BIGINT UNSIGNED NOT NULL, "
                        "`ingredient_id` BIGINT UNSIGNED NOT NULL, "
                        "`gross_qty_per_portion` DECIMAL(12, 3) NOT NULL COMMENT '单份毛菜：克或个数', "
                        "`sort_order` INT NOT NULL DEFAULT 0, "
                        "`created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                        "`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, "
                        "PRIMARY KEY (`id`), "
                        "UNIQUE KEY `uk_dish_prep_sop_dish_ingredient` (`dish_id`, `ingredient_id`), "
                        "KEY `idx_dish_prep_sop_store_dish` (`store_id`, `dish_id`), "
                        "KEY `idx_dish_prep_sop_ingredient` (`ingredient_id`), "
                        "CONSTRAINT `fk_dish_prep_sop_store` FOREIGN KEY (`store_id`) "
                        "REFERENCES `stores` (`id`) ON UPDATE CASCADE, "
                        "CONSTRAINT `fk_dish_prep_sop_dish` FOREIGN KEY (`dish_id`) "
                        "REFERENCES `menu_dish` (`id`) ON UPDATE CASCADE, "
                        "CONSTRAINT `fk_dish_prep_sop_ingredient` FOREIGN KEY (`ingredient_id`) "
                        "REFERENCES `prep_ingredient` (`id`) ON UPDATE CASCADE, "
                        "CONSTRAINT `chk_dish_prep_sop_qty` CHECK (`gross_qty_per_portion` > 0)"
                        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci "
                        "COMMENT='菜品配菜单份毛菜'"
                    )
                )
            logger.info("已创建 dish_prep_sop_line")


def apply_address_usage_data_backfill(db: Session) -> None:
    """把无餐次用户的地址标为零售，并把商城订单从餐次地址上解绑（复制后改绑）。"""
    from app.services.member.member_address_service import backfill_retail_address_separation

    backfill_retail_address_separation(db)
