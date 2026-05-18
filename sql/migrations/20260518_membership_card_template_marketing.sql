-- 会员卡模版：小程序展示字段（已执行过请勿重复整段运行）
-- 若某列已存在，请注释对应 ALTER 后再执行。

ALTER TABLE `membership_card_templates`
  ADD COLUMN `list_price_yuan` DECIMAL(12,2) NULL DEFAULT NULL COMMENT '原价（划线价，展示）' AFTER `meals_grant`;

ALTER TABLE `membership_card_templates`
  ADD COLUMN `sale_price_yuan` DECIMAL(12,2) NULL DEFAULT NULL COMMENT '优惠价（展示）' AFTER `list_price_yuan`;

ALTER TABLE `membership_card_templates`
  ADD COLUMN `card_style_image_url` VARCHAR(512) NULL DEFAULT NULL COMMENT '卡片样式图 URL' AFTER `sale_price_yuan`;

ALTER TABLE `membership_card_templates`
  ADD COLUMN `validity_days` INT NULL DEFAULT NULL COMMENT '有效天数（展示）' AFTER `card_style_image_url`;

ALTER TABLE `membership_card_templates`
  ADD COLUMN `intro_short` VARCHAR(512) NULL DEFAULT NULL COMMENT '商品简介' AFTER `validity_days`;

ALTER TABLE `membership_card_templates`
  ADD COLUMN `purchase_notice` TEXT NULL DEFAULT NULL COMMENT '购买须知' AFTER `intro_short`;
