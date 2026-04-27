-- 允许用户删除仍被历史单次订单引用的收货地址：删除地址时将订单上的 member_address_id 置为 NULL。
-- 配送快照已在 routing_area 等字段保留；原外键为 ON DELETE RESTRICT 会导致 DELETE 地址失败。

ALTER TABLE `single_meal_orders`
  DROP FOREIGN KEY `fk_smo_address`;

ALTER TABLE `single_meal_orders`
  ADD CONSTRAINT `fk_smo_address` FOREIGN KEY (`member_address_id`) REFERENCES `member_addresses` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE;
