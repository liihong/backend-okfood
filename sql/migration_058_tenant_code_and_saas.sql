-- SaaS 多租户：外部 tenantId（ext_json.tenantId）与 AppID 反查索引
-- 执行前请备份；对现网 OK饭 主租户（id=1）无行为变更，code 可留空

ALTER TABLE `tenants`
  ADD COLUMN `code` VARCHAR(64) NULL COMMENT 'SaaS 外部 tenantId，如 t_brand_a；与 ext_json.ext.tenantId 对齐' AFTER `name`;

-- MySQL 允许多行 code=NULL；非空 code 须唯一
CREATE UNIQUE INDEX `ux_tenants_code` ON `tenants` (`code`);

-- 微信 AppID 反查租户（登录/AppID 映射）
CREATE INDEX `ix_tis_wx_mini_appid` ON `tenant_integration_settings` (`wx_mini_appid`);
