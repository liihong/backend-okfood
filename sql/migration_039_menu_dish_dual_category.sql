-- 菜品库：肉类与菜品分类拆为两个独立字段
-- migration_039_menu_dish_dual_category.sql

ALTER TABLE `menu_dish`
  ADD COLUMN `meat_category_id` BIGINT UNSIGNED NULL COMMENT '肉类二级分类' AFTER `category_id`,
  ADD COLUMN `dish_type_category_id` BIGINT UNSIGNED NULL COMMENT '菜品分类二级分类' AFTER `meat_category_id`,
  ADD KEY `idx_menu_dish_meat_category` (`meat_category_id`),
  ADD KEY `idx_menu_dish_dish_type_category` (`dish_type_category_id`),
  ADD CONSTRAINT `fk_menu_dish_meat_category` FOREIGN KEY (`meat_category_id`) REFERENCES `product_category` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_menu_dish_dish_type_category` FOREIGN KEY (`dish_type_category_id`) REFERENCES `product_category` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE;

-- 将旧 category_id 按父级 code 迁移到新字段
UPDATE `menu_dish` md
INNER JOIN `product_category` pc ON md.`category_id` = pc.`id`
INNER JOIN `product_category` parent ON pc.`parent_id` = parent.`id`
SET
  md.`meat_category_id` = CASE WHEN parent.`code` = 'meat' THEN md.`category_id` ELSE md.`meat_category_id` END,
  md.`dish_type_category_id` = CASE WHEN parent.`code` = 'dish_type' THEN md.`category_id` ELSE md.`dish_type_category_id` END
WHERE md.`category_id` IS NOT NULL;
