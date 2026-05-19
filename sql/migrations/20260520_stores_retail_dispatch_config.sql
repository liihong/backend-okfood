-- 门店：单次点餐/商品单推顺丰专用店铺编号（与租户对接里的顺丰店铺、智能配送大表推单可不同）；UU 跑腿预留
ALTER TABLE `stores`
  ADD COLUMN `sf_retail_push_shop_id` VARCHAR(64) NULL COMMENT '零售单次推顺丰 shop_id，与大表推单租户 shop 区分' AFTER `sf_nightly_auto_push_enabled`,
  ADD COLUMN `sf_retail_push_shop_type` INT NULL COMMENT '顺丰 shop_type，空则与大表一致用租户/全局' AFTER `sf_retail_push_shop_id`,
  ADD COLUMN `uu_open_app_id` VARCHAR(64) NULL COMMENT 'UU跑腿 AppId（预留）' AFTER `sf_retail_push_shop_type`,
  ADD COLUMN `uu_open_app_key` VARCHAR(255) NULL COMMENT 'UU跑腿 AppKey（预留）' AFTER `uu_open_app_id`;
