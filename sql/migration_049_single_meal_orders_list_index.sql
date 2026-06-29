-- 管理端按供餐日分页列表：store_id + delivery_date 过滤后按 created_at/id 排序
ALTER TABLE `single_meal_orders`
  ADD KEY `idx_smo_store_date_created` (`store_id`, `delivery_date`, `created_at`, `id`);
