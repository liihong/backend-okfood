-- 会员退卡退款：按剩余次数比例退实收，供财务中心扣减统计
CREATE TABLE IF NOT EXISTS `member_membership_refunds` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` INT UNSIGNED NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `member_id` BIGINT UNSIGNED NOT NULL COMMENT 'members.id',
  `meals_consumed` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '退卡时已消费份数',
  `meals_refunded` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '本次退卡清零的剩余次数',
  `meal_quota_total` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '退卡前累计总次数（分母）',
  `paid_total_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '退卡时累计实收（元）',
  `unit_price_yuan` DECIMAL(12, 4) NOT NULL DEFAULT 0 COMMENT '单次单价（元）',
  `refund_amount_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '应退金额（元）',
  `remark` VARCHAR(500) NULL COMMENT '退卡备注',
  `operator` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '后台操作者',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_member_membership_refunds_member` (`member_id`),
  KEY `idx_member_membership_refunds_store_created` (`store_id`, `created_at`),
  CONSTRAINT `fk_member_membership_refunds_member`
    FOREIGN KEY (`member_id`) REFERENCES `members` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT `fk_member_membership_refunds_store`
    FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_member_membership_refunds_tenant`
    FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员退卡退款记录';
