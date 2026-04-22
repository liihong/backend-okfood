-- 开卡工单：小程序微信支付（JSAPI）商户单号与微信订单号
ALTER TABLE `member_card_orders`
  ADD COLUMN `out_trade_no` VARCHAR(32) NULL DEFAULT NULL COMMENT '微信 JSAPI 商户订单号（小程序自助开卡）' AFTER `applied_to_member`,
  ADD COLUMN `wx_transaction_id` VARCHAR(32) NULL DEFAULT NULL COMMENT '微信支付订单号' AFTER `out_trade_no`,
  ADD UNIQUE KEY `uk_member_card_orders_out_trade_no` (`out_trade_no`);
