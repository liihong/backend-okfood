-- 管理端系统消息：顺丰自动推单每日摘要等，管理员确认后不再展示
CREATE TABLE IF NOT EXISTS `admin_system_notifications` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL COMMENT 'stores.id',
  `kind` VARCHAR(50) NOT NULL COMMENT '通知类型，如 sf_nightly_push',
  `business_date` DATE NOT NULL COMMENT '关联业务日（上海）',
  `title` VARCHAR(200) NOT NULL COMMENT '列表/弹层标题',
  `message` VARCHAR(500) NOT NULL COMMENT '摘要正文',
  `total_count` INT NOT NULL DEFAULT 0 COMMENT '推送总数',
  `success_count` INT NOT NULL DEFAULT 0 COMMENT '成功数',
  `failed_count` INT NOT NULL DEFAULT 0 COMMENT '失败数',
  `skip_reason` VARCHAR(200) NULL COMMENT '未推单时的跳过原因',
  `acknowledged_at` DATETIME NULL COMMENT '管理员确认时间',
  `acknowledged_by` VARCHAR(100) NULL COMMENT '确认人 admin 用户名',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_admin_sys_notif_store_kind_date` (`store_id`, `kind`, `business_date`),
  KEY `idx_admin_sys_notif_store_unack` (`store_id`, `acknowledged_at`, `created_at`),
  CONSTRAINT `fk_admin_sys_notif_store`
    FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理端系统消息通知';
