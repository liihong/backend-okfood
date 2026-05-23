-- 续费提醒订阅消息额度：完善资料页授权 +1，低余额扣次成功下发后 -1
ALTER TABLE `members`
  ADD COLUMN `wx_renew_remind_quota` INT NOT NULL DEFAULT 0
    COMMENT '续费提醒订阅额度（每次授权+1，成功下发-1）'
  AFTER `last_low_balance_notify_date`;
