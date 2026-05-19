-- 顺丰创单记录：区分配送大表停靠点合并推单 vs 订单管理单次零售推单（监控筛选、履约回调分支）
ALTER TABLE `sf_same_city_pushes`
  ADD COLUMN `push_kind` VARCHAR(32) NOT NULL DEFAULT 'delivery_sheet'
    COMMENT 'delivery_sheet=大表停靠点; single_meal_retail=单次零售'
  AFTER `stop_id`;
