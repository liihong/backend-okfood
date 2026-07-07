-- 商城零售订单：后台备注（不对会员端展示）
ALTER TABLE `store_retail_orders`
  ADD COLUMN `remark` VARCHAR(500) NULL COMMENT '后台备注（不对会员端展示）' AFTER `sf_order_id`;
