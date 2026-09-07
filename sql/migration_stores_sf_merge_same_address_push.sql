-- 门店：同地址不同会员是否合并为一单推顺丰
-- 默认 0=按会员拆分（现网行为）；1=同址合并、扣一份配送费
-- 启动时 schema_patches.ensure_store_sf_merge_same_address_push_schema 会幂等补列

ALTER TABLE `stores`
  ADD COLUMN `sf_merge_same_address_push` TINYINT(1) NOT NULL DEFAULT 0
  COMMENT '同地址不同会员是否合并为一单推顺丰；0=按会员拆分（默认）'
  AFTER `sf_nightly_auto_push_enabled`;
