-- 地址、坐标、片区仅从 member_addresses 读取；删除 members 上对应冗余列。
-- 执行前请确认业务已以默认配送地址为准（migration_012 后应用层已不再写入这些列）。

ALTER TABLE `members`
  DROP INDEX `idx_members_area_active_balance`,
  DROP COLUMN `address`,
  DROP COLUMN `lng`,
  DROP COLUMN `lat`,
  DROP COLUMN `area`;

ALTER TABLE `members`
  ADD INDEX `idx_members_active_balance` (`is_active`, `balance`);
