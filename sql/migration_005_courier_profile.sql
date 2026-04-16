-- 配送员档案：电话、配送费待结算/已结算（元，两位小数）
ALTER TABLE `couriers`
  ADD COLUMN `phone` VARCHAR(20) NULL COMMENT '联系电话' AFTER `name`,
  ADD COLUMN `fee_pending` DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '配送费待结算(元)' AFTER `phone`,
  ADD COLUMN `fee_settled` DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '配送费已结算累计(元)' AFTER `fee_pending`;
