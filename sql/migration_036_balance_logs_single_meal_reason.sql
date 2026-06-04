-- 单次点餐会员卡扣次：balance_logs.reason 增加 single_meal
-- 未执行本迁移时，POST .../pay/member-balance 写入流水会触发 MySQL ENUM 错误（HTTP 500）

ALTER TABLE `balance_logs`
  MODIFY COLUMN `reason` ENUM(
    'recharge',
    'delivery',
    'refund',
    'admin_adjust',
    'single_meal'
  ) NOT NULL COMMENT 'admin_adjust=后台改次; single_meal=单点会员卡扣次';
