-- 会员起送日：仅当业务配送日 >= delivery_start_date 时进入配送大表/派单（NULL=不限制，兼容旧数据）
SET NAMES utf8mb4;

ALTER TABLE `members`
  ADD COLUMN `delivery_start_date` DATE NULL COMMENT '起送业务日(上海)：非空则仅当配送日>=该日才参与配送' AFTER `last_low_balance_notify_date`;

ALTER TABLE `member_card_orders`
  ADD COLUMN `delivery_start_date` DATE NULL COMMENT '约定起送业务日，同步入账时写入 members.delivery_start_date' AFTER `remark`;
