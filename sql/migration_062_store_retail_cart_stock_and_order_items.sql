-- 商城购物车：订单明细表 + 商品库存字段 + 历史订单回填

-- 1. 商品库存（NULL 表示不限库存）
ALTER TABLE `store_retail_products`
  ADD COLUMN `stock_quantity` INT UNSIGNED NULL DEFAULT NULL
    COMMENT '可售库存上限；NULL=不限' AFTER `is_on_shelf`;

-- 2. 订单明细
CREATE TABLE IF NOT EXISTS `store_retail_order_items` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `order_id` BIGINT UNSIGNED NOT NULL COMMENT 'store_retail_orders.id',
  `retail_product_id` BIGINT UNSIGNED NOT NULL,
  `category_id` BIGINT UNSIGNED NULL COMMENT '下单时品类快照',
  `product_title` VARCHAR(256) NOT NULL COMMENT '下单时商品名快照',
  `unit_price_yuan` DECIMAL(12, 2) NOT NULL COMMENT '下单时单价快照',
  `quantity` INT UNSIGNED NOT NULL DEFAULT 1,
  `line_amount_yuan` DECIMAL(12, 2) NOT NULL COMMENT '行小计',
  `sort_order` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_sroi_order` (`order_id`),
  KEY `idx_sroi_product` (`retail_product_id`),
  CONSTRAINT `fk_sroi_order` FOREIGN KEY (`order_id`) REFERENCES `store_retail_orders` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_sroi_product` FOREIGN KEY (`retail_product_id`) REFERENCES `store_retail_products` (`id`)
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商城零售订单明细';

-- 3. 历史订单回填（每单 1 行明细）
INSERT INTO `store_retail_order_items` (
  `order_id`,
  `retail_product_id`,
  `category_id`,
  `product_title`,
  `unit_price_yuan`,
  `quantity`,
  `line_amount_yuan`,
  `sort_order`,
  `created_at`
)
SELECT
  o.`id`,
  o.`retail_product_id`,
  p.`category_id`,
  o.`product_title`,
  CASE
    WHEN o.`quantity` > 0 THEN ROUND(o.`amount_yuan` / o.`quantity`, 2)
    ELSE o.`amount_yuan`
  END,
  o.`quantity`,
  o.`amount_yuan`,
  0,
  o.`created_at`
FROM `store_retail_orders` o
LEFT JOIN `store_retail_products` p ON p.`id` = o.`retail_product_id`
WHERE NOT EXISTS (
  SELECT 1 FROM `store_retail_order_items` i WHERE i.`order_id` = o.`id`
);
