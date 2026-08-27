-- 全餐卡「与午餐一起配送」跟卡走：模版配置 + 工单入账快照
-- 默认 0，现网午餐 / 分送全餐 / 纯晚餐行为不变

ALTER TABLE `membership_card_templates`
  ADD COLUMN `deliver_dinner_with_lunch` TINYINT(1) NOT NULL DEFAULT 0
    COMMENT '午+晚是否与午餐一起配送（午餐履约时连带扣晚餐）；仅 meal_periods 含午+晚时有效'
  AFTER `meal_periods`;

ALTER TABLE `member_card_orders`
  ADD COLUMN `deliver_dinner_with_lunch_snapshot` TINYINT(1) NOT NULL DEFAULT 0
    COMMENT '入账时从模版复制；true=午餐履约后连带扣晚餐'
  AFTER `meal_periods_snapshot`;

-- 租户 3 现有「午餐+晚餐」模版按运营约定为中午统一配送；只勾午餐/晚餐保持 0
UPDATE `membership_card_templates`
SET `deliver_dinner_with_lunch` = 1
WHERE `tenant_id` = 3
  AND JSON_CONTAINS(`meal_periods`, '"lunch"')
  AND JSON_CONTAINS(`meal_periods`, '"dinner"');

-- 已入账工单：仅绑定上述模版的跟卡快照回填，避免无模版导入单被误判
UPDATE `member_card_orders` AS `o`
INNER JOIN `membership_card_templates` AS `t`
  ON `o`.`membership_template_id` = `t`.`id`
SET `o`.`deliver_dinner_with_lunch_snapshot` = 1
WHERE `t`.`tenant_id` = 3
  AND `t`.`deliver_dinner_with_lunch` = 1
  AND `o`.`applied_to_member` = 1;
