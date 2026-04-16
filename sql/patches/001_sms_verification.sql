-- 若已执行过旧版 schema，可单独执行本补丁创建短信验证码表。
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `sms_verification` (
  `phone` VARCHAR(20) NOT NULL,
  `code` VARCHAR(10) NOT NULL,
  `expire_at` DATETIME NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`phone`),
  KEY `idx_sms_verification_expire` (`expire_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='短信登录验证码';
