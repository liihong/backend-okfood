-- 会员登记与配送系统 — 修订版表结构
-- MySQL 8.0+ / InnoDB / utf8mb4
-- 修订说明：
--   1) delivery_logs 增加 (user_id, delivery_date) 唯一约束，防止同日重复扣次
--   2) members 增加 last_low_balance_notify_date，低余额提醒去重
--   3) 新增 admin_users，管理端独立账号（勿与会员 Token 混用）
--   4) 配送员表注释与语句分离，避免复制执行错误
--   5) delivery_regions / delivery_region_couriers；member_addresses.delivery_region_id 外键对齐
--   6) 菜单拆为 menu_dish（菜品库，可启用/停用）与 menu_schedule（按日排期）；同月同一菜仅可排一天
--   7) product_category + menu_dish.category_id；weekly_menu_slot（week_start+slot）承载每周餐品，本周/下周仅差 week_start，无需翻周拷贝
--   8) menu_dish.image_url 为 TEXT，便于管理端长图链/Data URL
--   9) 存量库无菜品表时可执行 migration_011_menu_catalog_baseline.sql 补齐
--  10) members 不含地址/坐标/片区列，一律由 member_addresses 管理（见 migration_014）
--  11) member_card_orders 开卡工单（见 migration_017_member_card_orders.sql）
--  12) members.delivery_start_date / 工单起送日（见 migration_018_members_delivery_start_date.sql）
--  13) members 自增 id 主键、子表 member_id（见 migration_019_members_surrogate_id.sql）
--  14) members.wx_mini_openid小程序登录标识（见 migration_022_members_wx_mini_openid.sql）
--  15) 移除短信登录表 sms_verification（见 migration_023_drop_sms_verification.sql）
--  16) single_meal_orders 单次点餐（见 migration_024_single_meal_orders.sql）
--  17) single_meal_orders 微信字段（见 migration_025_single_meal_orders_wechat.sql）
--  18) members.daily_meal_units每配送日份数（见 migration_026_members_daily_meal_units.sql）
--  19) members.meal_quota_total周卡月卡累计总次数展示（见 migration_028_members_meal_quota_total.sql）
--  20) member_addresses.delivery_region_id 外键替代 area/area_manual（见 migration_029_member_addresses_delivery_region_id.sql）

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `members` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `phone` VARCHAR(20) NOT NULL COMMENT '手机号，登录与检索用，唯一',
  `name` VARCHAR(100) NOT NULL,
  `wechat_name` VARCHAR(100) NULL COMMENT '微信小程序昵称',
  `wx_mini_openid` VARCHAR(64) NULL COMMENT '微信小程序 openid',
  `remarks` VARCHAR(500) NULL COMMENT '忌口/备注',
  `avatar_url` VARCHAR(512) NULL COMMENT '头像 URL',
  `balance` INT NOT NULL DEFAULT 0 COMMENT '剩余配送次数',
  `daily_meal_units` INT NOT NULL DEFAULT 1 COMMENT '每配送日需送达份数；确认送达时按此倍数扣减 balance',
  `meal_quota_total` INT NOT NULL DEFAULT 0 COMMENT '周卡/月卡累计套餐总次数（展示分母）；工单入账与 balance 同额累加',
  `plan_type` ENUM('次卡','周卡','月卡') NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '计划是否开启',
  `is_leaved_tomorrow` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '仅明天请假',
  `leave_range_start` DATE NULL,
  `leave_range_end` DATE NULL,
  `last_low_balance_notify_date` DATE NULL COMMENT '最近一次低余额提醒的业务日(上海)，用于去重',
  `delivery_start_date` DATE NULL COMMENT '起送业务日(上海)：非空则仅当配送日>=该日才参与配送',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_members_phone` (`phone`),
  UNIQUE KEY `uk_members_wx_mini_openid` (`wx_mini_openid`),
  KEY `idx_members_active_balance` (`is_active`, `balance`),
  KEY `idx_members_balance_created` (`balance`, `created_at`),
  KEY `idx_members_leave_range` (`leave_range_start`, `leave_range_end`),
  CONSTRAINT `chk_members_balance_nonneg` CHECK (`balance` >= 0),
  CONSTRAINT `chk_members_daily_meal_units` CHECK (`daily_meal_units` >= 1 AND `daily_meal_units` <= 50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员';

CREATE TABLE IF NOT EXISTS `member_addresses` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `member_id` BIGINT UNSIGNED NOT NULL COMMENT 'members.id',
  `contact_name` VARCHAR(100) NOT NULL COMMENT '收件人',
  `contact_phone` VARCHAR(20) NOT NULL COMMENT '联系电话',
  `delivery_region_id` BIGINT UNSIGNED NULL COMMENT '配送片区 delivery_regions.id；未划区为 NULL',
  `detail_address` VARCHAR(500) NOT NULL COMMENT '详细地址（门牌/楼层等）',
  `remarks` VARCHAR(500) NULL COMMENT '忌口/备注',
  `lng` DECIMAL(11,8) NULL COMMENT '高德经度 GCJ-02',
  `lat` DECIMAL(11,8) NULL COMMENT '高德纬度 GCJ-02',
  `is_default` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否默认配送地址',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_member_addresses_member` (`member_id`),
  KEY `idx_member_addresses_member_default` (`member_id`, `is_default`),
  KEY `idx_member_addresses_delivery_region` (`delivery_region_id`),
  CONSTRAINT `fk_member_addresses_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_member_addresses_delivery_region` FOREIGN KEY (`delivery_region_id`) REFERENCES `delivery_regions` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员配送地址（多地址）';

CREATE TABLE IF NOT EXISTS `couriers` (
  `courier_id` VARCHAR(50) NOT NULL COMMENT '工号/配送员ID',
  `name` VARCHAR(100) NULL,
  `phone` VARCHAR(20) NULL COMMENT '联系电话',
  `fee_pending` DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '配送费待结算(元)',
  `fee_settled` DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '配送费已结算累计(元)',
  `pin_hash` VARCHAR(255) NOT NULL COMMENT 'PIN/密码 bcrypt哈希',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`courier_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配送员';

CREATE TABLE IF NOT EXISTS `delivery_regions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(64) NOT NULL COMMENT '片区展示名；与 member_addresses.delivery_region_id 解析结果一致',
  `code` VARCHAR(32) NULL COMMENT '可选业务编码',
  `polygon_json` JSON NOT NULL COMMENT '多边形外环 GCJ-02',
  `priority` INT NOT NULL DEFAULT 0 COMMENT '重叠时越小越优先',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_delivery_regions_active_priority` (`is_active`, `priority`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配送区域';

CREATE TABLE IF NOT EXISTS `delivery_region_couriers` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `region_id` BIGINT UNSIGNED NOT NULL,
  `courier_id` VARCHAR(50) NOT NULL,
  `is_primary` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '该区域主责/默认配送员，每区最多一名',
  `sort_order` INT NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_region_courier` (`region_id`, `courier_id`),
  KEY `idx_drc_region` (`region_id`),
  KEY `idx_drc_courier` (`courier_id`),
  CONSTRAINT `fk_drc_region` FOREIGN KEY (`region_id`) REFERENCES `delivery_regions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_drc_courier` FOREIGN KEY (`courier_id`) REFERENCES `couriers` (`courier_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配送区域与配送员绑定';

CREATE TABLE IF NOT EXISTS `admin_users` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_admin_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='后台管理员';

CREATE TABLE IF NOT EXISTS `delivery_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `member_id` BIGINT UNSIGNED NOT NULL COMMENT 'members.id',
  `delivery_date` DATE NOT NULL COMMENT '配送日期（业务日，Asia/Shanghai）',
  `status` ENUM('pending','delivered','leave') NOT NULL DEFAULT 'pending',
  `courier_id` VARCHAR(50) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_delivery_member_date` (`member_id`, `delivery_date`),
  KEY `idx_delivery_date_status` (`delivery_date`, `status`),
  CONSTRAINT `fk_delivery_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_delivery_courier` FOREIGN KEY (`courier_id`) REFERENCES `couriers` (`courier_id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配送流水';

CREATE TABLE IF NOT EXISTS `balance_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `member_id` BIGINT UNSIGNED NOT NULL,
  `change` INT NOT NULL COMMENT '正数充值/退款增加，负数扣减',
  `reason` ENUM('recharge','delivery','refund') NOT NULL,
  `operator` VARCHAR(50) NOT NULL COMMENT 'admin 用户名、courier_id或 system',
  `detail` VARCHAR(500) NULL COMMENT '业务说明：如开卡工单号、备注摘要等',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_balance_member_created` (`member_id`, `created_at`),
  CONSTRAINT `fk_balance_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='余额流水';

CREATE TABLE IF NOT EXISTS `member_card_orders` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `member_id` BIGINT UNSIGNED NOT NULL COMMENT 'members.id',
  `card_kind` ENUM('周卡','月卡') NOT NULL COMMENT '开卡类型',
  `pay_channel` ENUM('微信','支付宝') NOT NULL COMMENT '缴费渠道',
  `pay_status` ENUM('未缴','已缴') NOT NULL DEFAULT '未缴' COMMENT '缴费情况',
  `amount_yuan` DECIMAL(12,2) NULL COMMENT '实收金额(元)，可选',
  `remark` VARCHAR(500) NULL,
  `delivery_start_date` DATE NULL COMMENT '约定起送业务日，同步入账时写入 members.delivery_start_date',
  `applied_to_member` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已按周卡6次/月卡24次写入会员并更新 plan_type',
  `out_trade_no` VARCHAR(32) NULL DEFAULT NULL COMMENT '微信 JSAPI 商户订单号（小程序自助开卡）',
  `wx_transaction_id` VARCHAR(32) NULL DEFAULT NULL COMMENT '微信支付订单号',
  `created_by` VARCHAR(64) NOT NULL COMMENT '后台管理员用户名',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_member_card_orders_out_trade_no` (`out_trade_no`),
  KEY `idx_member_card_orders_member` (`member_id`),
  KEY `idx_member_card_orders_status_created` (`pay_status`, `created_at`),
  CONSTRAINT `fk_member_card_orders_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员开卡工单';

CREATE TABLE IF NOT EXISTS `product_category` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(32) NOT NULL COMMENT '业务编码，如 weekly',
  `name` VARCHAR(64) NOT NULL COMMENT '展示名',
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_product_category_code` (`code`),
  KEY `idx_product_category_active_sort` (`is_active`, `sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品分类';

INSERT INTO `product_category` (`code`, `name`, `sort_order`, `is_active`)
VALUES ('weekly', '每周餐品', 0, 1)
ON DUPLICATE KEY UPDATE `id` = `id`;

CREATE TABLE IF NOT EXISTS `menu_dish` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL COMMENT '菜品名称',
  `description` VARCHAR(1000) NULL,
  `image_url` TEXT NULL,
  `is_enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  `category_id` BIGINT UNSIGNED NULL COMMENT '所属分类（商品库）',
  `single_order_price_yuan` DECIMAL(12, 2) NULL COMMENT '单点售价(元)',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_menu_dish_enabled` (`is_enabled`),
  KEY `idx_menu_dish_category` (`category_id`),
  CONSTRAINT `fk_menu_dish_category` FOREIGN KEY (`category_id`) REFERENCES `product_category` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='菜品/商品库';

CREATE TABLE IF NOT EXISTS `weekly_menu_slot` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `week_start` DATE NOT NULL COMMENT '当周周一',
  `slot` TINYINT NOT NULL COMMENT '1=周一 … 7=周日',
  `dish_id` BIGINT UNSIGNED NOT NULL,
  `service_date` DATE AS (DATE_ADD(`week_start`, INTERVAL (`slot` - 1) DAY)) STORED,
  `service_ym` CHAR(7) AS (DATE_FORMAT(`service_date`, '%Y-%m')) STORED,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_weekly_slot_week_day` (`week_start`, `slot`),
  UNIQUE KEY `uk_weekly_dish_month` (`dish_id`, `service_ym`),
  KEY `idx_weekly_menu_week` (`week_start`),
  KEY `idx_weekly_menu_dish` (`dish_id`),
  CONSTRAINT `fk_weekly_menu_dish` FOREIGN KEY (`dish_id`) REFERENCES `menu_dish` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `chk_weekly_slot_range` CHECK (`slot` BETWEEN 1 AND 7)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每周餐品槽位';

CREATE TABLE IF NOT EXISTS `menu_schedule` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `menu_date` DATE NOT NULL COMMENT '配送/供餐业务日',
  `dish_id` BIGINT UNSIGNED NOT NULL,
  `schedule_ym` CHAR(7) AS (DATE_FORMAT(`menu_date`, '%Y-%m')) STORED COMMENT '自然月，用于同月菜品去重',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_menu_schedule_date` (`menu_date`),
  UNIQUE KEY `uk_schedule_dish_month` (`dish_id`, `schedule_ym`),
  KEY `idx_menu_schedule_dish` (`dish_id`),
  CONSTRAINT `fk_menu_schedule_dish` FOREIGN KEY (`dish_id`) REFERENCES `menu_dish` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日排期';

CREATE TABLE IF NOT EXISTS `app_settings` (
  `id` TINYINT UNSIGNED NOT NULL DEFAULT 1,
  `leave_deadline_time` TIME NOT NULL DEFAULT '21:00:00' COMMENT '每日请假截止时间（仅对「明天请假」等需当日截止的场景校验）',
  `store_name` VARCHAR(128) NULL DEFAULT NULL COMMENT '门店展示名称',
  `store_logo_url` VARCHAR(512) NULL DEFAULT NULL COMMENT '门店 Logo 图片 URL',
  `store_lng` DECIMAL(11, 8) NULL DEFAULT NULL COMMENT '门店 GCJ-02 经度（骑手排序与地图锚点）',
  `store_lat` DECIMAL(11, 8) NULL DEFAULT NULL COMMENT '门店 GCJ-02 纬度',
  `courier_delivery_base_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 4.00 COMMENT '骑手配送费：首份基础价（元）',
  `courier_delivery_extra_per_unit_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 1.00 COMMENT '骑手配送费：同地址每多一份加价（元）',
  `member_card_week_price_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 168.00 COMMENT '小程序周卡微信支付标价（元）',
  `member_card_month_price_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 669.00 COMMENT '小程序月卡微信支付标价（元）',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `chk_singleton_settings` CHECK (`id` = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='全局设置';

INSERT INTO `app_settings` (
  `id`,
  `leave_deadline_time`,
  `courier_delivery_base_yuan`,
  `courier_delivery_extra_per_unit_yuan`,
  `member_card_week_price_yuan`,
  `member_card_month_price_yuan`
)
VALUES (1, '21:00:00', 4.00, 1.00, 168.00, 669.00)
ON DUPLICATE KEY UPDATE `id` = `id`;

CREATE TABLE IF NOT EXISTS `single_meal_orders` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `out_trade_no` VARCHAR(32) NOT NULL COMMENT '商户订单号，微信统一下单',
  `member_id` BIGINT UNSIGNED NOT NULL COMMENT 'members.id',
  `dish_id` BIGINT UNSIGNED NOT NULL COMMENT 'menu_dish.id',
  `member_address_id` BIGINT UNSIGNED NOT NULL COMMENT 'member_addresses.id',
  `delivery_date` DATE NOT NULL COMMENT '供餐/配送业务日(上海)',
  `routing_area` VARCHAR(64) NOT NULL COMMENT '下单时片区快照',
  `amount_yuan` DECIMAL(12, 2) NOT NULL,
  `pay_status` ENUM('未支付', '已支付') NOT NULL DEFAULT '未支付',
  `pay_channel` VARCHAR(16) NULL,
  `wx_transaction_id` VARCHAR(32) NULL COMMENT '微信支付订单号',
  `fulfillment_status` VARCHAR(20) NOT NULL DEFAULT 'pending',
  `courier_id` VARCHAR(50) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_smo_out_trade_no` (`out_trade_no`),
  KEY `idx_smo_member_created` (`member_id`, `created_at`),
  KEY `idx_smo_date_area` (`delivery_date`, `routing_area`),
  KEY `idx_smo_courier_date_status` (`courier_id`, `delivery_date`, `fulfillment_status`),
  CONSTRAINT `fk_smo_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_smo_dish` FOREIGN KEY (`dish_id`) REFERENCES `menu_dish` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_smo_address` FOREIGN KEY (`member_address_id`) REFERENCES `member_addresses` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_smo_courier` FOREIGN KEY (`courier_id`) REFERENCES `couriers` (`courier_id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员单次点餐订单';

