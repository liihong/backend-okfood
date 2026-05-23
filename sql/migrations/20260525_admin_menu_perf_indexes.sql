-- 管理端菜品/周菜单接口性能：复合索引
-- 执行前请确认列已存在（多门店迁移后 weekly_menu_slot / menu_schedule / menu_dish 均含 store_id）
-- 若索引已存在会报错，可逐条跳过或先 SHOW INDEX FROM `表名`;

-- weekly_menu_slot：按门店+周查槽位（若已有 uk_weekly_slot_store_week_slot 则可跳过，前缀已覆盖）
-- ALTER TABLE `weekly_menu_slot`
--   ADD INDEX `idx_weekly_menu_slot_store_week` (`store_id`, `week_start`);

-- menu_schedule：按门店+日期批量查排期（若已有 uk_menu_schedule_store_date 则可跳过）
-- ALTER TABLE `menu_schedule`
--   ADD INDEX `idx_menu_schedule_store_date` (`store_id`, `menu_date`);

-- menu_dish：列表 WHERE store_id ORDER BY id DESC
ALTER TABLE `menu_dish`
  ADD INDEX `idx_menu_dish_store_id` (`store_id`, `id`);

-- single_meal_orders：周槽库存统计 GROUP BY delivery_date, dish_id
ALTER TABLE `single_meal_orders`
  ADD INDEX `idx_smo_store_date_pay_dish` (`store_id`, `delivery_date`, `pay_status`, `dish_id`);

-- members：订阅应配送份数 SUM（按门店+活跃+未删过滤）
ALTER TABLE `members`
  ADD INDEX `idx_members_store_active_deleted` (`store_id`, `is_active`, `deleted_at`);
