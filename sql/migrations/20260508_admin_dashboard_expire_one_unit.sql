-- 营业概览归档：今日到期（仅剩 1 次配送）会员数
ALTER TABLE `admin_dashboard_biz_day_snapshots`
  ADD COLUMN `today_expire_one_unit_members` INT NOT NULL DEFAULT 0
  COMMENT '锚定日应履约且 balance 恰等于每配送日份数（仅剩 1 次）的会员数'
  AFTER `tomorrow_meals_to_prepare`;
