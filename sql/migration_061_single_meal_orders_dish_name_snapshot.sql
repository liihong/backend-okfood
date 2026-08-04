-- 单次点餐：菜品名快照 + dish_id 可空，允许删除菜品库后保留历史订单

ALTER TABLE `single_meal_orders`
  ADD COLUMN `dish_name` VARCHAR(200) NULL
    COMMENT '下单时菜品名快照；菜品删除后仍可读'
  AFTER `dish_id`;

UPDATE `single_meal_orders` smo
INNER JOIN `menu_dish` md ON smo.`dish_id` = md.`id`
SET smo.`dish_name` = md.`name`
WHERE smo.`dish_name` IS NULL;

ALTER TABLE `single_meal_orders`
  DROP FOREIGN KEY `fk_smo_dish`;

ALTER TABLE `single_meal_orders`
  MODIFY COLUMN `dish_id` BIGINT UNSIGNED NULL COMMENT 'menu_dish.id；菜品删除后为 NULL';

ALTER TABLE `single_meal_orders`
  ADD CONSTRAINT `fk_smo_dish` FOREIGN KEY (`dish_id`) REFERENCES `menu_dish` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE;
