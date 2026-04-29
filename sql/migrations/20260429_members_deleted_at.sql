-- 会员档案逻辑删除：列表与统计排除 deleted_at 非空；释放手机号供重新注册
ALTER TABLE `members`
  ADD COLUMN `deleted_at` DATETIME NULL DEFAULT NULL COMMENT '逻辑删除时间；空表示正常' AFTER `created_at`,
  ADD KEY `idx_members_deleted_at` (`deleted_at`);
