-- 单次点餐订单：按地址片区快照派单至 delivery_region_couriers 主责骑手（或由业务后续调整）
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `single_meal_orders` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `member_id` BIGINT UNSIGNED NOT NULL COMMENT 'members.id',
  `dish_id` BIGINT UNSIGNED NOT NULL COMMENT 'menu_dish.id',
  `member_address_id` BIGINT UNSIGNED NOT NULL COMMENT 'member_addresses.id，下单快照',
  `delivery_date` DATE NOT NULL COMMENT '供餐/配送业务日(上海)',
  `routing_area` VARCHAR(64) NOT NULL COMMENT '下单时片区，与 member_addresses.area 一致',
  `amount_yuan` DECIMAL(12, 2) NOT NULL,
  `pay_status` ENUM('未支付', '已支付') NOT NULL DEFAULT '未支付',
  `pay_channel` VARCHAR(16) NULL COMMENT '如微信',
  `fulfillment_status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending | delivered',
  `courier_id` VARCHAR(50) NULL COMMENT '派单骑手，与 delivery_logs.courier_id 一致',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_smo_member_created` (`member_id`, `created_at`),
  KEY `idx_smo_date_area` (`delivery_date`, `routing_area`),
  KEY `idx_smo_courier_date_status` (`courier_id`, `delivery_date`, `fulfillment_status`),
  CONSTRAINT `fk_smo_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_smo_dish` FOREIGN KEY (`dish_id`) REFERENCES `menu_dish` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_smo_address` FOREIGN KEY (`member_address_id`) REFERENCES `member_addresses` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_smo_courier` FOREIGN KEY (`courier_id`) REFERENCES `couriers` (`courier_id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员单次点餐订单';
