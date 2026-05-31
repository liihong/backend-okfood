-- 会员操作审计日志（小程序暂停/恢复配送、改份数等；管理端档案变更）
CREATE TABLE IF NOT EXISTS `member_operation_logs` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `member_id` BIGINT NOT NULL COMMENT 'members.id',
  `source` VARCHAR(20) NOT NULL DEFAULT 'miniprogram' COMMENT 'miniprogram / admin',
  `operation_type` VARCHAR(50) NOT NULL COMMENT '操作类型代码',
  `summary` VARCHAR(200) NOT NULL COMMENT '列表展示摘要',
  `before_json` TEXT NULL COMMENT '变更前 JSON',
  `after_json` TEXT NULL COMMENT '变更后 JSON',
  `ip_address` VARCHAR(64) NULL COMMENT '客户端 IP',
  `operator` VARCHAR(100) NOT NULL DEFAULT '' COMMENT 'member:<id> 或 admin:<user>',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '北京时间 naive',
  PRIMARY KEY (`id`),
  KEY `ix_member_operation_logs_member_id` (`member_id`),
  KEY `ix_member_operation_logs_operation_type` (`operation_type`),
  KEY `ix_member_operation_logs_created_at` (`created_at`),
  CONSTRAINT `fk_member_operation_logs_member_id` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
