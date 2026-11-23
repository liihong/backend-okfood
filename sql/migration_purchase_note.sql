-- 采购资料。独立备忘，不关联菜品、库存和供应商。
-- 启动时 app.db.packaging_schema.ensure_packaging_schema 会幂等建表。

CREATE TABLE IF NOT EXISTS `purchase_note` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `category` VARCHAR(16) NOT NULL COMMENT 'ingredient=食材类，consumable=耗材类',
  `name` VARCHAR(64) NOT NULL,
  `record_method` VARCHAR(16) NOT NULL COMMENT 'link / wechat / phone / other',
  `contact_value` VARCHAR(500) NOT NULL COMMENT '链接、微信号、手机号或其他查找内容',
  `platform` VARCHAR(32) NULL COMMENT '如淘宝、拼多多、微信',
  `supplier_label` VARCHAR(64) NULL COMMENT '简称或供应方',
  `remark` VARCHAR(500) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_purchase_note_store` (`store_id`, `category`),
  CONSTRAINT `fk_purchase_note_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
