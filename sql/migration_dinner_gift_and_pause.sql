-- 晚餐单独暂停、指定配送日；会员卡赠送晚餐次数与果蔬汁 SKU。
-- 启动时 schema_patches.ensure_dinner_gift_schema 会幂等补列。
-- dinner_delivery_paused 默认 0：正式晚餐/全餐不受影响。赠送晚餐入账时由程序写成 1。

ALTER TABLE `member_meal_period_state`
  ADD COLUMN `dinner_delivery_paused` TINYINT(1) NOT NULL DEFAULT 0
  COMMENT '只暂停晚餐日程，不影响午餐';

ALTER TABLE `member_meal_period_state`
  ADD COLUMN `dinner_deliver_on` DATE NULL
  COMMENT '晚餐指定配送日；暂停时只在这一天进晚餐单';

ALTER TABLE `membership_card_templates`
  ADD COLUMN `gift_dinner_meals` INT NOT NULL DEFAULT 0
  COMMENT '赠送晚餐次数，不写入餐段快照';

ALTER TABLE `membership_card_templates`
  ADD COLUMN `gift_retail_product_id` BIGINT NULL
  COMMENT '赠送果蔬汁 SKU';

ALTER TABLE `membership_card_templates`
  ADD COLUMN `gift_retail_quantity` INT NOT NULL DEFAULT 0
  COMMENT '赠送果蔬汁单数，开卡时逐笔建单';
