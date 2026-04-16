-- 示例：商品分类 + 周槽位排期（2026-04-13 当周周一 ~ 周日）
-- 会员端优先读 weekly_menu_slot；与 menu_schedule 二选一维护即可，避免同日重复配置。
-- 可重复执行：删本周槽位及示例菜、按日排期中同周日期。

SET NAMES utf8mb4;

SET @ws := '2026-04-13';

DELETE FROM `weekly_menu_slot` WHERE `week_start` = @ws;

DELETE FROM `menu_schedule` WHERE `menu_date` BETWEEN @ws AND DATE_ADD(@ws, INTERVAL 6 DAY);

DELETE FROM `menu_dish` WHERE `name` IN (
  '红烧肉套餐',
  '黑椒牛柳意面',
  '清蒸鲈鱼套餐',
  '宫保鸡丁饭',
  '咖喱鸡排饭',
  '周末轻食盒',
  '周日家常小炒'
);

INSERT INTO `menu_dish` (`name`, `description`, `image_url`, `is_enabled`, `category_id`)
SELECT v.`name`, v.`description`, NULL, 1, `c`.`id`
FROM (
  SELECT '红烧肉套餐' AS `name`, '红烧肉、米饭、番茄炒蛋、紫菜蛋花汤' AS `description`
  UNION ALL SELECT '黑椒牛柳意面', '牛柳、意面、西兰花、例汤'
  UNION ALL SELECT '清蒸鲈鱼套餐', '鲈鱼半条、米饭、蒜蓉娃娃菜、冬瓜排骨汤'
  UNION ALL SELECT '宫保鸡丁饭', '鸡丁、花生、青椒、米饭、酸辣汤'
  UNION ALL SELECT '咖喱鸡排饭', '鸡排、咖喱土豆、米饭、罗宋汤'
  UNION ALL SELECT '周末轻食盒', '鸡胸、藜麦饭、牛油果沙拉、酸奶'
  UNION ALL SELECT '周日家常小炒', '回锅肉、麻婆豆腐、米饭、青菜豆腐汤'
) AS v
INNER JOIN `product_category` `c` ON `c`.`code` = 'weekly';

INSERT INTO `weekly_menu_slot` (`week_start`, `slot`, `dish_id`) VALUES
  (@ws, 1, (SELECT `id` FROM `menu_dish` WHERE `name` = '红烧肉套餐' LIMIT 1)),
  (@ws, 2, (SELECT `id` FROM `menu_dish` WHERE `name` = '黑椒牛柳意面' LIMIT 1)),
  (@ws, 3, (SELECT `id` FROM `menu_dish` WHERE `name` = '清蒸鲈鱼套餐' LIMIT 1)),
  (@ws, 4, (SELECT `id` FROM `menu_dish` WHERE `name` = '宫保鸡丁饭' LIMIT 1)),
  (@ws, 5, (SELECT `id` FROM `menu_dish` WHERE `name` = '咖喱鸡排饭' LIMIT 1)),
  (@ws, 6, (SELECT `id` FROM `menu_dish` WHERE `name` = '周末轻食盒' LIMIT 1)),
  (@ws, 7, (SELECT `id` FROM `menu_dish` WHERE `name` = '周日家常小炒' LIMIT 1));
