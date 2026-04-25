-- 顺丰同城推单历史（管理端「发送到顺丰」）
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `sf_same_city_pushes` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `delivery_date` DATE NOT NULL COMMENT '配送业务日(上海)',
  `stop_id` VARCHAR(64) NOT NULL COMMENT '与预览接口一致的停靠点稳定 id',
  `shop_order_id` VARCHAR(64) NOT NULL COMMENT '商家订单号(唯一)',
  `sf_order_id` VARCHAR(32) NULL DEFAULT NULL COMMENT '顺丰侧订单号(成功时)',
  `sf_bill_id` VARCHAR(32) NULL DEFAULT NULL COMMENT '运单号(若有返回)',
  `error_code` INT NULL DEFAULT NULL,
  `error_msg` VARCHAR(1024) NULL DEFAULT NULL,
  `request_snapshot` JSON NULL COMMENT '当次提交的业务快照(可含 14 项模板字段)',
  `response_json` JSON NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sf_same_city_pushes_shop_order` (`shop_order_id`),
  KEY `idx_sf_same_city_pushes_date_stop` (`delivery_date`, `stop_id`),
  KEY `idx_sf_same_city_pushes_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='顺丰同城创单记录';
