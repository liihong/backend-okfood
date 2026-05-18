-- 门店：顺丰夜间自动推单（每日 22:00 上海时区推送次日业务日）
-- MySQL / MariaDB

ALTER TABLE `stores`
  ADD COLUMN `sf_nightly_auto_push_enabled` TINYINT(1) NOT NULL DEFAULT 0
    COMMENT '每日22:00自动顺丰推次日单;0=仅手动'
  AFTER `is_active`;
