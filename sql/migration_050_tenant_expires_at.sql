-- 租户按年订阅到期日（含当日仍有效）
ALTER TABLE `tenants`
  ADD COLUMN `expires_at` DATE NULL DEFAULT NULL
    COMMENT '按年订阅到期日（含当日仍有效）' AFTER `is_active`,
  ADD KEY `ix_tenants_expires_at` (`expires_at`);
