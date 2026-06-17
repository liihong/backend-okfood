-- 午/晚餐分离：模版餐段、工单快照、配送流水餐段、推单快照分餐段、晚餐运营态表
-- 历史数据一律 backfill 为 lunch，保证现有午餐链路语义不变

ALTER TABLE `membership_card_templates`
  ADD COLUMN `meal_periods` JSON NOT NULL
    COMMENT '覆盖餐段：["lunch"] / ["dinner"] / ["lunch","dinner"]'
    DEFAULT ('["lunch"]')
  AFTER `period_kind`;

ALTER TABLE `member_card_orders`
  ADD COLUMN `meal_periods_snapshot` JSON NULL
    COMMENT '入账时从模版复制的餐段快照；经典周/月/次卡为 ["lunch"]'
  AFTER `membership_template_id`;

UPDATE `member_card_orders`
SET `meal_periods_snapshot` = JSON_ARRAY('lunch'),
    `updated_at` = `updated_at`
WHERE `applied_to_member` = 1 AND `meal_periods_snapshot` IS NULL;

ALTER TABLE `delivery_logs`
  ADD COLUMN `meal_period` VARCHAR(16) NOT NULL DEFAULT 'lunch'
    COMMENT '履约餐段：lunch=午餐配送；dinner=晚餐配送'
  AFTER `delivery_date`;

ALTER TABLE `delivery_logs`
  DROP INDEX `uk_delivery_member_date`;

ALTER TABLE `delivery_logs`
  ADD UNIQUE KEY `uk_delivery_member_date_period` (`member_id`, `delivery_date`, `meal_period`);

ALTER TABLE `delivery_sheet_push_units_snapshots`
  ADD COLUMN `meal_period` VARCHAR(16) NOT NULL DEFAULT 'lunch'
    COMMENT '推单快照所属餐段'
  AFTER `delivery_date`;

ALTER TABLE `delivery_sheet_push_units_snapshots`
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (`store_id`, `delivery_date`, `meal_period`);

ALTER TABLE `delivery_sheet_push_absent_snapshots`
  ADD COLUMN `meal_period` VARCHAR(16) NOT NULL DEFAULT 'lunch'
    COMMENT '请假快照所属餐段'
  AFTER `delivery_date`;

ALTER TABLE `delivery_sheet_push_absent_snapshots`
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (`store_id`, `delivery_date`, `meal_period`);

CREATE TABLE IF NOT EXISTS `member_meal_period_state` (
  `member_id` BIGINT UNSIGNED NOT NULL COMMENT 'members.id',
  `meal_period` VARCHAR(16) NOT NULL COMMENT '本期仅 dinner 使用；午餐仍用 members 表字段',
  `daily_meal_units` INT NOT NULL DEFAULT 1 COMMENT '该餐段每配送日份数',
  `daily_meal_units_pending` INT NULL DEFAULT NULL COMMENT '预约下一配送日生效份数',
  `is_leaved_tomorrow` TINYINT(1) NOT NULL DEFAULT 0,
  `tomorrow_leave_target_date` DATE NULL DEFAULT NULL,
  `leave_range_start` DATE NULL DEFAULT NULL,
  `leave_range_end` DATE NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`member_id`, `meal_period`),
  CONSTRAINT `fk_mmps_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='分餐段运营态（份数/请假）；资格仍由开卡工单 meal_periods_snapshot 决定';
