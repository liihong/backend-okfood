-- 明日快速请假：记录实际不配送的业务日，便于统计/配送与「请假中」状态延续至该日 24:00
ALTER TABLE `members`
  ADD COLUMN `tomorrow_leave_target_date` DATE NULL
    COMMENT '仅明日请假：不配送的目标业务日（上海）；为 NULL 时沿用旧版仅 is_leaved_tomorrow 语义'
  AFTER `is_leaved_tomorrow`;
