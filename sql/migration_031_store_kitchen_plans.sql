-- 后厨计划出单（营业概览顶卡联动）
CREATE TABLE IF NOT EXISTS `store_kitchen_plans` (
  `store_id` BIGINT UNSIGNED NOT NULL,
  `business_date` DATE NOT NULL COMMENT '上海业务日',
  `planned_total` INT NOT NULL COMMENT '后厨计划出单总数',
  `updated_by` VARCHAR(64) NULL,
  `updated_at` DATETIME NOT NULL,
  PRIMARY KEY (`store_id`, `business_date`),
  CONSTRAINT `fk_store_kitchen_plans_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
