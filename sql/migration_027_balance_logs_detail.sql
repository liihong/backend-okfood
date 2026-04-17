-- 余额流水增加业务说明字段，用于开卡工单同步入账等场景追溯
ALTER TABLE `balance_logs`
  ADD COLUMN `detail` VARCHAR(500) NULL COMMENT '业务说明：如开卡工单号、备注摘要等' AFTER `operator`;
