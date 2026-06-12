-- 开卡工单：pay_channel 支持「抖音」团购验券渠道
-- 原 ENUM('微信','支付宝','线下') 会导致抖音验券开卡 INSERT 失败（Data truncated）
-- migration_045_member_card_orders_pay_channel_douyin.sql

ALTER TABLE `member_card_orders`
  MODIFY COLUMN `pay_channel` VARCHAR(10) NOT NULL COMMENT '缴费渠道：微信/支付宝/线下/抖音';
