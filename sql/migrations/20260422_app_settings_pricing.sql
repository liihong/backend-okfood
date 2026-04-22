-- 全局设置：骑手配送费计价、小程序会员卡标价（后台「门店配置」可改）
ALTER TABLE `app_settings`
  ADD COLUMN `courier_delivery_base_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 4.00 COMMENT '骑手配送费：首份基础价（元）' AFTER `store_lat`,
  ADD COLUMN `courier_delivery_extra_per_unit_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 1.00 COMMENT '骑手配送费：同地址每多一份加价（元）' AFTER `courier_delivery_base_yuan`,
  ADD COLUMN `member_card_week_price_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 168.00 COMMENT '小程序周卡微信支付标价（元）' AFTER `courier_delivery_extra_per_unit_yuan`,
  ADD COLUMN `member_card_month_price_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 669.00 COMMENT '小程序月卡微信支付标价（元）' AFTER `member_card_week_price_yuan`;
