-- 同 SPU 下规格名唯一（空规格视为「默认」，不可重复）
-- 执行前请确认无重复数据；若有需先手工合并或改名

UPDATE `store_retail_products`
SET `spec_label` = NULL
WHERE `spec_label` IS NOT NULL AND TRIM(`spec_label`) = '';

ALTER TABLE `store_retail_products`
  ADD COLUMN `spec_label_key` VARCHAR(128) GENERATED ALWAYS AS (COALESCE(`spec_label`, '')) STORED
    COMMENT '规格唯一键，空=默认' AFTER `spec_label`;

ALTER TABLE `store_retail_products`
  ADD UNIQUE KEY `uk_srp_spu_spec` (`spu_id`, `spec_label_key`);
