-- 晚餐次数独立：member_meal_period_state 存晚餐剩余/总次数；balance_logs 区分餐段

ALTER TABLE `member_meal_period_state`
  ADD COLUMN `balance` INT NOT NULL DEFAULT 0
    COMMENT '该餐段剩余次数（本期晚餐使用；午餐仍用 members.balance）'
    AFTER `leave_range_end`,
  ADD COLUMN `meal_quota_total` INT NOT NULL DEFAULT 0
    COMMENT '该餐段累计总次数'
    AFTER `balance`;

ALTER TABLE `balance_logs`
  ADD COLUMN `meal_period` VARCHAR(16) NOT NULL DEFAULT 'lunch'
    COMMENT 'lunch=午餐次数池；dinner=晚餐次数池'
    AFTER `member_id`;
