-- 单次订单：微信 v2 商户单号、微信交易号
SET NAMES utf8mb4;

ALTER TABLE `single_meal_orders`
  ADD COLUMN `out_trade_no` VARCHAR(32) NULL COMMENT '商户订单号，微信统一下单' AFTER `id`,
  ADD COLUMN `wx_transaction_id` VARCHAR(32) NULL COMMENT '微信支付订单号 transaction_id' AFTER `pay_channel`;

UPDATE `single_meal_orders` SET `out_trade_no` = CONCAT('OKF', `id`) WHERE `out_trade_no` IS NULL;

ALTER TABLE `single_meal_orders`
  MODIFY `out_trade_no` VARCHAR(32) NOT NULL,
  ADD UNIQUE KEY `uk_smo_out_trade_no` (`out_trade_no`);
