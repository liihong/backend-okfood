-- 午/晚餐分餐段：周菜单、后厨计划、单次零售、损耗流水、概览快照
-- 依赖 migration_046（delivery_logs / 推单快照 meal_period）

-- 1) 周菜单槽位分餐段
ALTER TABLE `weekly_menu_slot`
  ADD COLUMN `meal_period` VARCHAR(16) NOT NULL DEFAULT 'lunch'
    COMMENT 'lunch=午餐槽；dinner=晚餐槽'
  AFTER `slot`;

ALTER TABLE `weekly_menu_slot`
  DROP INDEX `uk_weekly_slot_store_week_slot`;

ALTER TABLE `weekly_menu_slot`
  ADD UNIQUE KEY `uk_weekly_slot_store_week_slot_period` (`store_id`, `week_start`, `slot`, `meal_period`);

-- 2) 按日排期分餐段
ALTER TABLE `menu_schedule`
  ADD COLUMN `meal_period` VARCHAR(16) NOT NULL DEFAULT 'lunch'
    COMMENT 'lunch/dinner'
  AFTER `menu_date`;

ALTER TABLE `menu_schedule`
  DROP INDEX `uk_menu_schedule_store_date`;

ALTER TABLE `menu_schedule`
  ADD UNIQUE KEY `uk_menu_schedule_store_date_period` (`store_id`, `menu_date`, `meal_period`);

-- 3) 后厨计划分餐段
ALTER TABLE `store_kitchen_plans`
  ADD COLUMN `meal_period` VARCHAR(16) NOT NULL DEFAULT 'lunch'
    COMMENT 'lunch/dinner'
  AFTER `business_date`;

ALTER TABLE `store_kitchen_plans`
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (`store_id`, `business_date`, `meal_period`);

-- 4) 单次零售分餐段
ALTER TABLE `single_meal_orders`
  ADD COLUMN `meal_period` VARCHAR(16) NOT NULL DEFAULT 'lunch'
    COMMENT '占用哪一餐段日库存'
  AFTER `delivery_date`;

ALTER TABLE `single_meal_orders`
  ADD KEY `idx_smo_store_date_period` (`store_id`, `delivery_date`, `meal_period`);

-- 5) 日库存损耗流水（禁止直接改剩余，仅通过流水）
CREATE TABLE IF NOT EXISTS `day_stock_adjustment_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `business_date` DATE NOT NULL COMMENT '上海业务日',
  `meal_period` VARCHAR(16) NOT NULL COMMENT 'lunch/dinner',
  `delta` INT NOT NULL COMMENT '负数减可售；正数回补',
  `reason_code` VARCHAR(32) NOT NULL COMMENT 'spill/kitchen_taste/kitchen_waste/comp_meal/count_correction/other',
  `remark` VARCHAR(500) NULL,
  `operator` VARCHAR(64) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_day_stock_adj_store_date_period` (`store_id`, `business_date`, `meal_period`, `created_at`),
  CONSTRAINT `fk_day_stock_adj_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='日库存损耗/回补流水；剩余=后厨出餐-分配+sum(delta)';

-- 6) 营业概览快照分餐段 + 后厨出餐归档
ALTER TABLE `admin_dashboard_biz_day_snapshots`
  ADD COLUMN `meal_period` VARCHAR(16) NOT NULL DEFAULT 'lunch'
    COMMENT 'lunch/dinner'
  AFTER `business_anchor_date`;

ALTER TABLE `admin_dashboard_biz_day_snapshots`
  ADD COLUMN `kitchen_output_total` INT NULL DEFAULT NULL
    COMMENT '锚定日后厨出餐份数归档；未配置则为 NULL'
  AFTER `today_meals_to_prepare`;

ALTER TABLE `admin_dashboard_biz_day_snapshots`
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (`store_id`, `business_anchor_date`, `meal_period`);
