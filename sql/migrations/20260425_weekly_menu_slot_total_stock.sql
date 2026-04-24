-- 日总份与单次卡上限：存于 weekly_menu_slot.total_stock（NULL=不限制）
ALTER TABLE `weekly_menu_slot`
  ADD COLUMN `total_stock` INT UNSIGNED NULL DEFAULT NULL
  COMMENT '日总份(含订阅与单次)；NULL=不限制单次卡'
  AFTER `dish_id`;

-- 若曾使用旧表 menu_day_stock，在加列后另执行 20260425b_migrate_from_menu_day_stock.sql
