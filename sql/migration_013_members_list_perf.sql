-- 管理端会员列表：WHERE balance … + ORDER BY created_at DESC 走索引，显著减少全表扫描
-- MySQL 8+ / InnoDB

ALTER TABLE `members`
  ADD INDEX `idx_members_balance_created` (`balance`, `created_at`);
