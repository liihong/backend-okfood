-- 会员自助操作审计日志：暂停/恢复配送、修改配送份数、修改配送地址等
-- 面向争议取证：记录谁、何时、在何 IP、做了什么变更，before/after 保留 JSON 便于还原
CREATE TABLE IF NOT EXISTS `member_operation_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `member_id` BIGINT UNSIGNED NOT NULL COMMENT 'members.id',
  `source` VARCHAR(20) NOT NULL DEFAULT 'miniprogram' COMMENT '操作来源：miniprogram/admin',
  `operation_type` VARCHAR(50) NOT NULL COMMENT '操作类型代码',
  `summary` VARCHAR(200) NOT NULL COMMENT '操作摘要（直观展示）',
  `before_json` TEXT NULL COMMENT '变更前字段 JSON',
  `after_json` TEXT NULL COMMENT '变更后字段 JSON',
  `ip_address` VARCHAR(64) NULL COMMENT '客户端 IP',
  `operator` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '操作者：member:<id> 或 admin:<username>',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_member_operation_logs_member_created` (`member_id`, `created_at`),
  KEY `idx_member_operation_logs_operation_type` (`operation_type`),
  KEY `idx_member_operation_logs_created_at` (`created_at`),
  CONSTRAINT `fk_member_operation_logs_member`
    FOREIGN KEY (`member_id`) REFERENCES `members` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员自助操作日志';
