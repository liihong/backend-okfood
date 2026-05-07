-- 营业概览与配送大表口径对齐的历史快照表
CREATE TABLE IF NOT EXISTS `admin_dashboard_biz_day_snapshots` (
  `business_anchor_date` DATE NOT NULL COMMENT '统计锚定业务日(上海)',
  `today_leave_members` INT NOT NULL,
  `today_meals_to_prepare` INT NOT NULL,
  `tomorrow_leave_members` INT NOT NULL,
  `tomorrow_meals_to_prepare` INT NOT NULL,
  `recorded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`business_anchor_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
