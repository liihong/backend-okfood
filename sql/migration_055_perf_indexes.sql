-- 查询性能优化索引
-- 1. couriers.phone：登录时精确匹配，避免全表扫描
-- 2. member_card_orders (member_id, created_by, pay_status)：批量排查「小程序待完善」会员
-- 3. member_addresses (member_id, is_default)：默认地址批量加载的覆盖索引

-- couriers 手机号登录索引
ALTER TABLE `couriers`
  ADD KEY `idx_couriers_phone` (`phone`);

-- 小程序已付款工单批量查询（eligible_members_for_delivery 使用）
ALTER TABLE `member_card_orders`
  ADD KEY `idx_mco_miniprogram_paid` (`member_id`, `created_by`, `pay_status`);

-- 默认地址批量加载覆盖索引（load_default_address_map 使用）
ALTER TABLE `member_addresses`
  ADD KEY `idx_member_addresses_member_default` (`member_id`, `is_default`);
