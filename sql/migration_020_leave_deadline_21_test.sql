-- 测试用：将「明天请假」当日截止时间改为 21:00（恢复生产可改回 18:00:00）
UPDATE `app_settings`
SET `leave_deadline_time` = '21:00:00'
WHERE `id` = 1;
