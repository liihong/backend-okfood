-- 管理端会员档案库列表：store + 未删除 + 套餐类型 + 最近操作时间排序
ALTER TABLE `members`
  ADD KEY `idx_members_store_archive_updated` (`store_id`, `deleted_at`, `plan_type`, `updated_at`);

-- 生命周期批量：各会员最近已入账工单的 activation_mode
ALTER TABLE `member_card_orders`
  ADD KEY `idx_mco_member_applied_id` (`member_id`, `applied_to_member`, `id`);
