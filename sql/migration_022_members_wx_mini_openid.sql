-- 微信小程序 openid：登录时写入/更新，便于后续订阅消息等能力
ALTER TABLE `members`
  ADD COLUMN `wx_mini_openid` VARCHAR(64) NULL COMMENT '微信小程序 openid' AFTER `wechat_name`,
  ADD UNIQUE KEY `uk_members_wx_mini_openid` (`wx_mini_openid`);
