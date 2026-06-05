-- 抖音验券流水：保存核销 verify_id，供撤销 SPI 回调匹配
-- migration_038_douyin_redemption_verify_id.sql

ALTER TABLE `douyin_certificate_redemptions`
  ADD COLUMN `douyin_verify_id` VARCHAR(64) NULL DEFAULT NULL COMMENT '抖音验券返回 verify_id' AFTER `verify_token`,
  ADD KEY `idx_dcr_verify_id` (`douyin_verify_id`);
