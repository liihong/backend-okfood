-- 代码与 schema.sql 含 wx_transaction_id，旧库未执行时 INSERT 报错:
-- Unknown column 'wx_transaction_id' in 'field list'
-- 在业务库执行一次（与 .env 中 MYSQL_DATABASE 一致）。

ALTER TABLE `single_meal_orders`
  ADD COLUMN `wx_transaction_id` VARCHAR(32) NULL COMMENT '微信支付订单号' AFTER `pay_channel`;
