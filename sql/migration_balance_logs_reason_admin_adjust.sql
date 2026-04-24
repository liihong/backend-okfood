-- 管理端会员档案修改余额时写入 balance_logs.reason=admin_adjust（与 app.models.enums.BalanceReason 一致）。
-- 若库表仍为旧 ENUM，执行本脚本后重试保存。

ALTER TABLE `balance_logs`
  MODIFY COLUMN `reason` ENUM('recharge','delivery','refund','admin_adjust') NOT NULL
  COMMENT '业务原因：含后台人工调整剩余次数';
