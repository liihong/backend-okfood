-- 门店自提：不参与配送线路，仍参与订阅备餐与请假/起送日规则
ALTER TABLE `members`
  ADD COLUMN `store_pickup` TINYINT(1) NOT NULL DEFAULT 0
    COMMENT '门店自提：1 则不进骑手任务与按地址配送大表，单独归组'
  AFTER `delivery_deferred`;
