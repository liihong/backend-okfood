-- 管理员展示名称：登录后与操作记录中便于识别操作人（登录账号仍为 username/手机号）
ALTER TABLE `admin_users`
  ADD COLUMN `display_name` VARCHAR(64) NULL DEFAULT NULL COMMENT '管理员展示名称' AFTER `username`;
