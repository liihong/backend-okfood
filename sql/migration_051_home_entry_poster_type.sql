-- home_entry_poster 增加 poster_type 区分场景；删除误建的 menu_page_poster 表
-- migration_051_home_entry_poster_type.sql

ALTER TABLE `home_entry_poster`
  ADD COLUMN `poster_type` VARCHAR(32) NOT NULL DEFAULT 'entry'
  COMMENT '海报场景：entry=进入小程序 menu=菜单页'
  AFTER `store_id`;

UPDATE `home_entry_poster` SET `poster_type` = 'entry' WHERE `poster_type` = '' OR `poster_type` IS NULL;

ALTER TABLE `home_entry_poster`
  ADD UNIQUE KEY `uk_home_entry_poster_store_type` (`store_id`, `poster_type`);

ALTER TABLE `home_entry_poster` DROP INDEX `uk_home_entry_poster_store`;

DROP TABLE IF EXISTS `menu_page_poster`;
