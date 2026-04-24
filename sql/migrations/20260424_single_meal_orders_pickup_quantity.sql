-- 单次点餐：门店自提、多份计价；自提时无配送地址
ALTER TABLE `single_meal_orders`
  ADD COLUMN `store_pickup` TINYINT(1) NOT NULL DEFAULT 0
    COMMENT '门店自提：支付后不派骑手，履约直接完成'
    AFTER `member_address_id`,
  ADD COLUMN `quantity` INT UNSIGNED NOT NULL DEFAULT 1
    COMMENT '份数：总价=单价×份数；骑手确认送达时配送费按此份数计'
    AFTER `store_pickup`;

ALTER TABLE `single_meal_orders`
  MODIFY COLUMN `member_address_id` BIGINT UNSIGNED NULL
    COMMENT 'member_addresses.id；门店自提时为 NULL';
