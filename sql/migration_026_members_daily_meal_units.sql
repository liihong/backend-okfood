-- members：每配送日份数（多张周卡等场景下同日多份）
-- 在业务库执行（与 .env 中 MYSQL_DATABASE 一致）。
-- 可重复执行：已有列/约束时跳过，避免二次执行报错。

SET @db := DATABASE();

SELECT COUNT(*) INTO @col_exists
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'members' AND COLUMN_NAME = 'daily_meal_units';

SET @sql_col := IF(
  @col_exists = 0,
  'ALTER TABLE `members` ADD COLUMN `daily_meal_units` INT NOT NULL DEFAULT 1 COMMENT ''每配送日需送达份数；确认送达时按此倍数扣减 balance'' AFTER `balance`',
  'SELECT 1'
);
PREPARE stmt_col FROM @sql_col;
EXECUTE stmt_col;
DEALLOCATE PREPARE stmt_col;

SELECT COUNT(*) INTO @chk_exists
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'members' AND CONSTRAINT_NAME = 'chk_members_daily_meal_units';

SET @sql_chk := IF(
  @chk_exists = 0,
  'ALTER TABLE `members` ADD CONSTRAINT `chk_members_daily_meal_units` CHECK (`daily_meal_units` >= 1 AND `daily_meal_units` <= 50)',
  'SELECT 1'
);
PREPARE stmt_chk FROM @sql_chk;
EXECUTE stmt_chk;
DEALLOCATE PREPARE stmt_chk;
