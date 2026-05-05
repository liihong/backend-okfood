-- 后台账号角色：full=完整管理后台；delivery=仅配送相关接口与前端菜单
ALTER TABLE `admin_users`
  ADD COLUMN `role` VARCHAR(16) NOT NULL DEFAULT 'full' COMMENT 'full | delivery' AFTER `password_hash`;
