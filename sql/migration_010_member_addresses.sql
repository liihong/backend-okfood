-- 会员多地址：每条记录对应一个配送点（收件人、电话、区域、详细地址、备注、坐标、是否默认）
CREATE TABLE IF NOT EXISTS `member_addresses` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `member_phone` VARCHAR(20) NOT NULL COMMENT 'members.phone',
  `contact_name` VARCHAR(100) NOT NULL COMMENT '收件人',
  `contact_phone` VARCHAR(20) NOT NULL COMMENT '联系电话',
  `area` VARCHAR(64) NOT NULL COMMENT '配送区域名，与 members.area 语义一致',
  `detail_address` VARCHAR(500) NOT NULL COMMENT '详细地址（门牌/楼层等）',
  `remarks` VARCHAR(500) NULL COMMENT '忌口/备注',
  `lng` DECIMAL(11,8) NULL COMMENT '高德经度 GCJ-02',
  `lat` DECIMAL(11,8) NULL COMMENT '高德纬度 GCJ-02',
  `is_default` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否默认配送地址',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_member_addresses_member` (`member_phone`),
  KEY `idx_member_addresses_member_default` (`member_phone`, `is_default`),
  CONSTRAINT `fk_member_addresses_member` FOREIGN KEY (`member_phone`) REFERENCES `members` (`phone`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员配送地址（多地址）';
