-- 普通商品目录（幂等）+ 商城零售订单

CREATE TABLE IF NOT EXISTS `store_retail_categories` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_store_retail_cat_store_name` (`store_id`, `name`),
  KEY `idx_src_store` (`store_id`),
  CONSTRAINT `fk_src_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店普通商品分类';

CREATE TABLE IF NOT EXISTS `store_retail_products` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `category_id` BIGINT UNSIGNED NULL,
  `sku_code` VARCHAR(64) NULL,
  `title` VARCHAR(256) NOT NULL,
  `subtitle` VARCHAR(512) NULL,
  `description` TEXT NULL,
  `unit_price_yuan` DECIMAL(12, 2) NOT NULL,
  `list_price_yuan` DECIMAL(12, 2) NULL,
  `cover_image_url` VARCHAR(512) NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_on_shelf` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_srp_store` (`store_id`),
  KEY `idx_srp_category` (`category_id`),
  CONSTRAINT `fk_srp_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_srp_category` FOREIGN KEY (`category_id`) REFERENCES `store_retail_categories` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店普通商品 SKU';

CREATE TABLE IF NOT EXISTS `store_retail_orders` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` INT UNSIGNED NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `out_trade_no` VARCHAR(32) NOT NULL,
  `member_id` BIGINT UNSIGNED NOT NULL,
  `retail_product_id` BIGINT UNSIGNED NOT NULL,
  `product_title` VARCHAR(256) NOT NULL COMMENT '下单时商品名快照',
  `member_address_id` BIGINT UNSIGNED NULL,
  `store_pickup` TINYINT(1) NOT NULL DEFAULT 0,
  `quantity` INT UNSIGNED NOT NULL DEFAULT 1,
  `fulfillment_date` DATE NOT NULL COMMENT '履约业务日（服务端写入上海当日）',
  `routing_area` VARCHAR(64) NOT NULL,
  `amount_yuan` DECIMAL(12, 2) NOT NULL,
  `original_amount_yuan` DECIMAL(12, 2) NULL,
  `coupon_discount_yuan` DECIMAL(12, 2) NULL,
  `member_coupon_id` BIGINT UNSIGNED NULL,
  `pay_status` VARCHAR(10) NOT NULL DEFAULT '未支付',
  `pay_channel` VARCHAR(16) NULL,
  `wx_transaction_id` VARCHAR(32) NULL,
  `fulfillment_status` VARCHAR(20) NOT NULL DEFAULT 'pending',
  `courier_id` VARCHAR(50) NULL,
  `sf_same_city_push_id` BIGINT UNSIGNED NULL,
  `sf_order_id` VARCHAR(32) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sro_store_out_trade_no` (`store_id`, `out_trade_no`),
  KEY `idx_sro_member_created` (`member_id`, `created_at`),
  KEY `idx_sro_store_fulfillment` (`store_id`, `fulfillment_date`),
  KEY `idx_sro_member_coupon` (`member_coupon_id`),
  CONSTRAINT `fk_sro_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`)
    ON UPDATE CASCADE,
  CONSTRAINT `fk_sro_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`)
    ON UPDATE CASCADE,
  CONSTRAINT `fk_sro_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`)
    ON UPDATE CASCADE,
  CONSTRAINT `fk_sro_product` FOREIGN KEY (`retail_product_id`) REFERENCES `store_retail_products` (`id`)
    ON UPDATE CASCADE,
  CONSTRAINT `fk_sro_address` FOREIGN KEY (`member_address_id`) REFERENCES `member_addresses` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_sro_member_coupon` FOREIGN KEY (`member_coupon_id`) REFERENCES `member_coupons` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_sro_courier` FOREIGN KEY (`courier_id`) REFERENCES `couriers` (`courier_id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商城零售订单（普通商品）';
