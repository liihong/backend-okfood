-- 小程序自助暂停：生效业务日起才不进大表，当天仍配送
-- 启动时 schema_patches.ensure_members_pause_effective_date_schema 会幂等补列

ALTER TABLE `members`
  ADD COLUMN `pause_effective_date` DATE NULL
  COMMENT '小程序自助暂停生效业务日；有值且<=履约日则不进大表，当天仍配送'
  AFTER `delivery_deferred`;
