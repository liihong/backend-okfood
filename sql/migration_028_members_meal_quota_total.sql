-- members：周卡/月卡累计总次数（与 balance 组成剩余/总 展示）；入账时与剩余次数同步累加
-- 在业务库执行（与 .env 中 MYSQL_DATABASE 一致）。可重复执行。

SET @db := DATABASE();

SELECT COUNT(*) INTO @col_exists
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'members' AND COLUMN_NAME = 'meal_quota_total';

SET @sql_col := IF(
  @col_exists = 0,
  'ALTER TABLE `members` ADD COLUMN `meal_quota_total` INT NOT NULL DEFAULT 0 COMMENT ''周卡/月卡累计套餐总次数（展示分母）；工单同步入账时与 balance 同额累加'' AFTER `daily_meal_units`',
  'SELECT 1'
);
PREPARE stmt_col FROM @sql_col;
EXECUTE stmt_col;
DEALLOCATE PREPARE stmt_col;

-- 历史数据：按「剩余与套餐基准」较大值回填分母，避免上线后展示从空开始
UPDATE `members`
SET `meal_quota_total` = GREATEST(
  COALESCE(`balance`, 0),
  CASE COALESCE(`plan_type`, '')
    WHEN '周卡' THEN 6
    WHEN '月卡' THEN 24
    ELSE 0
  END
)
WHERE `meal_quota_total` = 0;
