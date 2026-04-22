-- 已有库增量：门店配置字段（与 sql/schema.sql 对齐）
ALTER TABLE `app_settings`
  ADD COLUMN `store_name` VARCHAR(128) NULL DEFAULT NULL COMMENT '门店展示名称' AFTER `leave_deadline_time`,
  ADD COLUMN `store_logo_url` VARCHAR(512) NULL DEFAULT NULL COMMENT '门店 Logo 图片 URL' AFTER `store_name`,
  ADD COLUMN `store_lng` DECIMAL(11, 8) NULL DEFAULT NULL COMMENT '门店 GCJ-02 经度（骑手排序与地图锚点）' AFTER `store_logo_url`,
  ADD COLUMN `store_lat` DECIMAL(11, 8) NULL DEFAULT NULL COMMENT '门店 GCJ-02 纬度' AFTER `store_lng`;
