-- 顺丰同城开放平台 HTTP 推送回调日志 + 关联推单行上的最近状态（便于后台查看）
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `sf_same_city_callbacks` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `route_kind` VARCHAR(64) NOT NULL COMMENT '与 /api/sf-open/notify/* 路由对应，如 delivery_status',
  `sign_ok` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '验签是否通过',
  `error_message` VARCHAR(512) NULL DEFAULT NULL COMMENT '验签失败或解析异常时的说明',
  `shop_order_id` VARCHAR(128) NULL DEFAULT NULL COMMENT '从 JSON 中提取的 merchant 单号（若有）',
  `sf_order_id` VARCHAR(64) NULL DEFAULT NULL COMMENT '从 JSON 中提取的顺丰单号（若有）',
  `payload_json` JSON NULL COMMENT '解析后的 JSON 对象（若可解析）',
  `raw_body` MEDIUMTEXT NOT NULL COMMENT '原始请求正文',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_sf_cb_shop_order` (`shop_order_id`),
  KEY `idx_sf_cb_sf_order` (`sf_order_id`),
  KEY `idx_sf_cb_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='顺丰同城开放平台回调';


ALTER TABLE `sf_same_city_pushes`
  ADD COLUMN `last_callback_at` DATETIME NULL DEFAULT NULL COMMENT '最近一次顺丰推送时间' AFTER `created_at`,
  ADD COLUMN `last_callback_kind` VARCHAR(64) NULL DEFAULT NULL COMMENT '最近一次回调类型' AFTER `last_callback_at`,
  ADD COLUMN `sf_callback_order_status` INT NULL DEFAULT NULL COMMENT '配送状态推送中的 order_status(见顺丰文档)' AFTER `last_callback_kind`;
