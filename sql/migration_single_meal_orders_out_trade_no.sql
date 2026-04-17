-- 单次点餐表缺少 out_trade_no 时出现: Unknown column 'out_trade_no' in 'field list'
-- 在业务库执行一次（与 .env 中 MYSQL_DATABASE 一致）。

ALTER TABLE `single_meal_orders`
  ADD COLUMN `out_trade_no` VARCHAR(32) NULL COMMENT '商户订单号，微信统一下单' AFTER `id`;

UPDATE `single_meal_orders`
SET `out_trade_no` = CONCAT(
  'MIG',
  LPAD(`id`, 12, '0'),
  SUBSTRING(MD5(CONCAT(IFNULL(`created_at`, NOW()), '-', `id`)), 1, 8)
)
WHERE `out_trade_no` IS NULL OR TRIM(`out_trade_no`) = '';

ALTER TABLE `single_meal_orders`
  MODIFY `out_trade_no` VARCHAR(32) NOT NULL COMMENT '商户订单号，微信统一下单';

ALTER TABLE `single_meal_orders`
  ADD UNIQUE KEY `uk_smo_out_trade_no` (`out_trade_no`);
