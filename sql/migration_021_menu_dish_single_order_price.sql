-- 菜品库：单点售价（元），可选；用于会员端展示与上单定价
SET NAMES utf8mb4;

ALTER TABLE `menu_dish`
  ADD COLUMN `single_order_price_yuan` DECIMAL(12, 2) NULL COMMENT '单点售价(元)' AFTER `category_id`;
