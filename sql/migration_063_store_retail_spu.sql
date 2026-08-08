-- 普通商品三层模型：分类 → SPU(商品) → SKU(store_retail_products)
-- 将现有 SKU 按 id 顺序 1:1 迁移为 SPU（避免 title 重复导致错绑）
-- 注意：本脚本仅执行一次；重复执行会因列/约束已存在而失败

-- 1. 商品 SPU 表
CREATE TABLE IF NOT EXISTS `store_retail_spus` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `category_id` BIGINT UNSIGNED NULL,
  `title` VARCHAR(256) NOT NULL COMMENT '商品名称',
  `subtitle` VARCHAR(512) NULL COMMENT '副标题/卖点',
  `detail_html` MEDIUMTEXT NULL COMMENT '富文本详情',
  `gallery_urls` JSON NULL COMMENT '轮播图 URL 列表，首项为列表封面',
  `purchase_notice` TEXT NULL COMMENT '购买须知',
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_on_shelf` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'SPU 总开关',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_srs_store` (`store_id`),
  KEY `idx_srs_category` (`category_id`),
  CONSTRAINT `fk_srs_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_srs_category` FOREIGN KEY (`category_id`) REFERENCES `store_retail_categories` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店普通商品 SPU';

-- 2. SKU 表增加 SPU 关联与规格名（若已存在则跳过需手工处理）
ALTER TABLE `store_retail_products`
  ADD COLUMN `spu_id` BIGINT UNSIGNED NULL COMMENT '所属商品 SPU' AFTER `store_id`,
  ADD COLUMN `spec_label` VARCHAR(128) NULL COMMENT '规格展示名，如 1日体验' AFTER `sku_code`;

-- 3. 按 SKU id 顺序生成 SPU（1:1）
INSERT INTO `store_retail_spus` (
  `store_id`,
  `category_id`,
  `title`,
  `subtitle`,
  `detail_html`,
  `gallery_urls`,
  `sort_order`,
  `is_on_shelf`,
  `created_at`,
  `updated_at`
)
SELECT
  p.`store_id`,
  p.`category_id`,
  p.`title`,
  p.`subtitle`,
  p.`description`,
  CASE
    WHEN p.`cover_image_url` IS NOT NULL AND TRIM(p.`cover_image_url`) != ''
    THEN JSON_ARRAY(p.`cover_image_url`)
    ELSE NULL
  END,
  p.`sort_order`,
  p.`is_on_shelf`,
  p.`created_at`,
  p.`updated_at`
FROM `store_retail_products` p
ORDER BY p.`id` ASC;

-- 4. 按行号一一回写 spu_id（INSERT 与 SELECT 均为 id 升序，故行号对齐）
UPDATE `store_retail_products` p
INNER JOIN (
  SELECT `id`, ROW_NUMBER() OVER (ORDER BY `id` ASC) AS `rn`
  FROM `store_retail_products`
) pr ON pr.`id` = p.`id`
INNER JOIN (
  SELECT `id`, ROW_NUMBER() OVER (ORDER BY `id` ASC) AS `rn`
  FROM `store_retail_spus`
) sr ON sr.`rn` = pr.`rn`
SET p.`spu_id` = sr.`id`
WHERE p.`spu_id` IS NULL;

-- 5. spu_id 必填 + 外键
ALTER TABLE `store_retail_products`
  MODIFY COLUMN `spu_id` BIGINT UNSIGNED NOT NULL,
  ADD KEY `idx_srp_spu` (`spu_id`),
  ADD CONSTRAINT `fk_srp_spu` FOREIGN KEY (`spu_id`) REFERENCES `store_retail_spus` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE;

-- 6. 订单明细增加 SPU 快照字段
ALTER TABLE `store_retail_order_items`
  ADD COLUMN `spu_id` BIGINT UNSIGNED NULL COMMENT '下单时 SPU 快照' AFTER `retail_product_id`,
  ADD COLUMN `spu_title` VARCHAR(256) NULL COMMENT '下单时商品名快照' AFTER `product_title`,
  ADD COLUMN `spec_label` VARCHAR(128) NULL COMMENT '下单时规格快照' AFTER `spu_title`;

UPDATE `store_retail_order_items` i
INNER JOIN `store_retail_products` p ON p.`id` = i.`retail_product_id`
INNER JOIN `store_retail_spus` s ON s.`id` = p.`spu_id`
SET
  i.`spu_id` = s.`id`,
  i.`spu_title` = s.`title`,
  i.`spec_label` = p.`spec_label`,
  i.`category_id` = COALESCE(i.`category_id`, s.`category_id`);

-- 7. 移除 SKU 表上的 SPU 级冗余字段
ALTER TABLE `store_retail_products`
  DROP FOREIGN KEY `fk_srp_category`,
  DROP KEY `idx_srp_category`,
  DROP COLUMN `category_id`,
  DROP COLUMN `title`,
  DROP COLUMN `subtitle`,
  DROP COLUMN `description`,
  DROP COLUMN `cover_image_url`;

ALTER TABLE `store_retail_products` COMMENT='门店普通商品 SKU';
