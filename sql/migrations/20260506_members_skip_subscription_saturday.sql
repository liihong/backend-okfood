-- 会员固定周六不参与订阅履约（到家+自提备餐）；0=与既有行为一致
ALTER TABLE `members`
  ADD COLUMN `skip_subscription_saturday` TINYINT(1) NOT NULL DEFAULT 0
  COMMENT '固定周六不参与订阅履约（全局日历仍为履约日时生效）'
  AFTER `store_pickup`;
