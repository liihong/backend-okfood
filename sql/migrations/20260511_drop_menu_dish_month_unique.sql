-- 菜单管理：取消「同一自然月内同一道菜仅出现一次」约束，允许同月重复排同一道菜。
-- MySQL / MariaDB

ALTER TABLE `weekly_menu_slot` DROP INDEX `uk_weekly_dish_month`;
ALTER TABLE `menu_schedule` DROP INDEX `uk_schedule_dish_month`;
