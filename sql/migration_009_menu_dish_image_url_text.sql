-- 菜品配图支持较长外链或 Data URL（管理端本地上传）
ALTER TABLE `menu_dish` MODIFY COLUMN `image_url` TEXT NULL;
