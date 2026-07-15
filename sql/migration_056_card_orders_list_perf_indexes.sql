-- 管理端开卡工单列表：store 过滤 + created_at/id 排序（含 include_history 全量历史）
ALTER TABLE `member_card_orders`
  ADD KEY `idx_mco_store_created_id` (`store_id`, `created_at`, `id`);

-- 待处理工作台：store + 未完结（未缴或已缴未入账）+ 缴费状态筛选
ALTER TABLE `member_card_orders`
  ADD KEY `idx_mco_store_applied_pay_created` (`store_id`, `applied_to_member`, `pay_status`, `created_at`, `id`);
