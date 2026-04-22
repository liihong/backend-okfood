-- 小程序「暂不配送」：与无起送日区分，避免资料页强制闭环
ALTER TABLE `members`
  ADD COLUMN `delivery_deferred` TINYINT(1) NOT NULL DEFAULT 0
    COMMENT '用户选择暂不配送：清空/无视起送日且 is_active=0，不计入开卡排期'
  AFTER `delivery_start_date`;
