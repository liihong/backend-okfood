-- 随餐饮饮品库，以及菜品上的配餐饮。启动时 schema_patches.ensure_menu_drink_schema 会幂等补齐。
-- 表或列已存在时不要重复执行。

CREATE TABLE IF NOT EXISTS `menu_drink` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(200) NOT NULL COMMENT '饮品名称',
  `description` VARCHAR(1000) NULL COMMENT '随餐说明',
  `image_url` TEXT NULL,
  `is_enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_menu_drink_store` (`store_id`),
  CONSTRAINT `fk_menu_drink_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='随餐饮饮品，供菜品配餐饮选用';

ALTER TABLE `menu_dish`
  ADD COLUMN `paired_drink_id` BIGINT NULL
  COMMENT '配餐饮，menu_drink.id，可空'
  AFTER `dish_type_category_id`;
