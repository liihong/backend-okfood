-- 商城普通商品：分类级配送费规则 + 订单商品/配送金额拆分
-- 启动时 app.db.schema_patches.ensure_retail_delivery_fee_schema 会幂等补列；本文件供手工执行。

ALTER TABLE `store_retail_categories`
  ADD COLUMN `delivery_pricing_mode` VARCHAR(16) NOT NULL DEFAULT 'included'
    COMMENT 'included=单价已含配送；extra_rule=按 delivery_rule 另计配送费'
    AFTER `is_active`;

ALTER TABLE `store_retail_categories`
  ADD COLUMN `delivery_rule` JSON NULL
    COMMENT 'extra_rule 时生效，如 qty_threshold_fee'
    AFTER `delivery_pricing_mode`;

ALTER TABLE `store_retail_orders`
  ADD COLUMN `goods_amount_yuan` DECIMAL(12, 2) NULL
    COMMENT '商品行小计（不含配送费）；历史单为空'
    AFTER `amount_yuan`;

ALTER TABLE `store_retail_orders`
  ADD COLUMN `delivery_fee_yuan` DECIMAL(12, 2) NULL
    COMMENT '配送费合计；历史单为空视为 0'
    AFTER `goods_amount_yuan`;