-- 开卡工单：关联会员卡模版（自律卡包微信下单入账餐次以此为准）
-- 列已存在时请跳过。

ALTER TABLE `member_card_orders`
  ADD COLUMN `membership_template_id` BIGINT UNSIGNED NULL DEFAULT NULL
    COMMENT 'membership_card_templates.id；空表示经典周/月卡'
    AFTER `member_id`,
  ADD KEY `idx_mco_membership_template` (`membership_template_id`),
  ADD CONSTRAINT `fk_mco_membership_template`
    FOREIGN KEY (`membership_template_id`) REFERENCES `membership_card_templates` (`id`)
    ON UPDATE CASCADE ON DELETE SET NULL;
