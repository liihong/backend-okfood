-- 会员头像 URL（可选，如对象存储 HTTPS地址）
ALTER TABLE `members`
  ADD COLUMN `avatar_url` VARCHAR(512) NULL COMMENT '头像 URL' AFTER `remarks`;
