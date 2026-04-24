-- 仅当库中已存在旧表 `menu_day_stock`（且已先执行 20260425 为 weekly_menu_slot 增加 total_stock 列）时整段执行。
-- 新库可忽略本文件。

UPDATE `weekly_menu_slot` w
INNER JOIN `menu_day_stock` m
  ON m.menu_date = DATE_ADD(w.`week_start`, INTERVAL (w.`slot` - 1) DAY)
  AND m.dish_id = w.dish_id
SET w.`total_stock` = m.`total_stock`;

DROP TABLE IF EXISTS `menu_day_stock`;
