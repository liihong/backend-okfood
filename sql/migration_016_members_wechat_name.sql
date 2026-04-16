-- 会员微信小程序昵称（与 name 区分，便于后台展示）
ALTER TABLE `members`
  ADD COLUMN `wechat_name` VARCHAR(100) NULL COMMENT '微信小程序昵称' AFTER `name`;
