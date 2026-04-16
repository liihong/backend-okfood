-- 会员开卡工单：记录周卡/月卡、微信/支付宝缴费情况及后台入账标记
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `member_card_orders` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `member_phone` VARCHAR(20) NOT NULL COMMENT 'members.phone',
  `card_kind` ENUM('周卡','月卡') NOT NULL COMMENT '开卡类型',
  `pay_channel` ENUM('微信','支付宝') NOT NULL COMMENT '缴费渠道',
  `pay_status` ENUM('未缴','已缴') NOT NULL DEFAULT '未缴' COMMENT '缴费情况',
  `amount_yuan` DECIMAL(12,2) NULL COMMENT '实收金额(元)，可选',
  `remark` VARCHAR(500) NULL,
  `applied_to_member` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已按周卡6次/月卡24次写入会员并更新 plan_type',
  `created_by` VARCHAR(64) NOT NULL COMMENT '后台管理员用户名',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_member_card_orders_phone` (`member_phone`),
  KEY `idx_member_card_orders_status_created` (`pay_status`, `created_at`),
  CONSTRAINT `fk_member_card_orders_member` FOREIGN KEY (`member_phone`) REFERENCES `members` (`phone`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员开卡工单';
