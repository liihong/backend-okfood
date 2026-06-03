-- 配送大表首次顺丰推单当日：请假会员快照（推单后 merged 白名单扩容用）
CREATE TABLE IF NOT EXISTS `delivery_sheet_push_absent_snapshots` (
  `store_id` BIGINT NOT NULL,
  `delivery_date` DATE NOT NULL COMMENT '上海业务配送日',
  `absent_member_ids` JSON NOT NULL COMMENT '首次推单时刻该日请假会员 id 数组',
  `recorded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`store_id`, `delivery_date`),
  CONSTRAINT `fk_ds_push_absent_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
