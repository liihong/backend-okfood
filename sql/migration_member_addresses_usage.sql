-- 会员地址拆分：餐次送餐(meal) 与 果蔬汁/月饼等商城收货(retail) 互不共用、互不改写
-- 启动时 app.db.schema_patches 会幂等补列并回填；本文件供手工执行。

ALTER TABLE `member_addresses`
  ADD COLUMN `address_usage` VARCHAR(16) NOT NULL DEFAULT 'meal'
    COMMENT 'meal=会员送餐地址；retail=果蔬汁/月饼等商城收货地址'
    AFTER `is_default`;

ALTER TABLE `member_addresses`
  ADD INDEX `idx_member_addresses_member_usage_default` (`member_id`, `address_usage`, `is_default`);
