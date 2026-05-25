-- 会员退卡状态 + 退款流水补全已消费扣款字段
ALTER TABLE `members`
  ADD COLUMN `membership_refunded_at` DATETIME NULL COMMENT '退卡退款确认时刻；非空则档案状态为已退款' AFTER `deleted_at`,
  ADD KEY `idx_members_membership_refunded_at` (`membership_refunded_at`);

ALTER TABLE `member_membership_refunds`
  ADD COLUMN `consumed_value_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '已消费扣款（按各日菜单单价）' AFTER `paid_total_yuan`;

-- 历史退卡：从流水表回填会员退卡时刻
UPDATE `members` m
INNER JOIN (
  SELECT `member_id`, MIN(`created_at`) AS `refunded_at`
  FROM `member_membership_refunds`
  GROUP BY `member_id`
) r ON r.`member_id` = m.`id`
SET m.`membership_refunded_at` = r.`refunded_at`
WHERE m.`membership_refunded_at` IS NULL;
