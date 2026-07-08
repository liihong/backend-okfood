-- 开卡工单入账意图（v3：不在 members 表增加状态枚举）
ALTER TABLE member_card_orders
  ADD COLUMN activation_mode VARCHAR(32) NULL
  COMMENT 'explicit_date|keep_schedule|defer_not_open|defer_pause；NULL=历史工单按 legacy 推断'
  AFTER delivery_start_date;
