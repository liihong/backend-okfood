-- 微信开放平台：component verify_ticket + 租户 authorizer token 落库
-- OK饭 主租户不使用 authorizer 时，本表无行亦不影响直连 AppID/Secret 登录

CREATE TABLE IF NOT EXISTS `wx_open_component_state` (
  `id` INT NOT NULL PRIMARY KEY COMMENT '固定 1',
  `verify_ticket` VARCHAR(512) NULL COMMENT '微信每 10 分钟推送的 component_verify_ticket',
  `ticket_updated_at` DATETIME NULL,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='第三方平台 component 全局状态';

INSERT INTO `wx_open_component_state` (`id`, `verify_ticket`, `ticket_updated_at`, `updated_at`)
VALUES (1, NULL, NULL, NOW())
ON DUPLICATE KEY UPDATE `id` = `id`;

ALTER TABLE `tenant_integration_settings`
  ADD COLUMN `wx_authorizer_access_token` VARCHAR(512) NULL COMMENT '代授权小程序 access_token' AFTER `wx_mini_secret`,
  ADD COLUMN `wx_authorizer_refresh_token` VARCHAR(512) NULL COMMENT '代授权 refresh_token，用于刷新' AFTER `wx_authorizer_access_token`,
  ADD COLUMN `wx_authorizer_token_expires_at` DATETIME NULL COMMENT 'authorizer_access_token 过期时间' AFTER `wx_authorizer_refresh_token`,
  ADD COLUMN `wx_authorizer_authorized_at` DATETIME NULL COMMENT '最近一次授权/刷新成功时间' AFTER `wx_authorizer_token_expires_at`;
