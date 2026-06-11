-- 方案 B：会员改份数写入 pending，次日 00:01 生效
ALTER TABLE `members`
  ADD COLUMN `daily_meal_units_pending` INT NULL DEFAULT NULL
    COMMENT '预约次日生效的每配送日份数；NULL 表示无待生效变更'
  AFTER `daily_meal_units`;

-- 方案 A：首次大表顺丰推单当日快照各会员份数（冻结日大表统计用）
-- 与 delivery_sheet_push_absent_snapshots 同结构；不加 FK 避免 stores.id 类型/字符集不一致导致建表失败
CREATE TABLE IF NOT EXISTS `delivery_sheet_push_units_snapshots` (
  `store_id` BIGINT NOT NULL,
  `delivery_date` DATE NOT NULL COMMENT '上海业务配送日',
  `member_meal_units` JSON NOT NULL COMMENT '首次推单时刻 member_id→份数 映射（键为字符串）',
  `recorded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`store_id`, `delivery_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
