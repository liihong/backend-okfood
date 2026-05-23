-- 租户对接：续费提醒订阅消息模板 ID
ALTER TABLE `tenant_integration_settings`
  ADD COLUMN `wx_subscribe_renew_tmpl_id` VARCHAR(128) NULL
    COMMENT '续费提醒订阅消息模板 ID；空则回退全局 .env'
  AFTER `wx_subscribe_delivery_tmpl_id`;
