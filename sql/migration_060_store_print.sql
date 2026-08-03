-- 门店打印机配置、场景绑定、打印任务日志；租户云打印开发者凭证

ALTER TABLE `tenant_integration_settings`
  ADD COLUMN `feie_user` VARCHAR(64) NULL COMMENT '飞鹅云开发者 USER' AFTER `extra_json`,
  ADD COLUMN `feie_ukey` VARCHAR(128) NULL COMMENT '飞鹅云开发者 UKEY' AFTER `feie_user`,
  ADD COLUMN `xprinter_user` VARCHAR(64) NULL COMMENT '芯烨云开发者账号' AFTER `feie_ukey`,
  ADD COLUMN `xprinter_user_key` VARCHAR(128) NULL COMMENT '芯烨云 UserKEY' AFTER `xprinter_user`,
  ADD COLUMN `yilian_partner` VARCHAR(32) NULL COMMENT '易联云应用 partner/id' AFTER `xprinter_user_key`,
  ADD COLUMN `yilian_apikey` VARCHAR(128) NULL COMMENT '易联云应用 apikey' AFTER `yilian_partner`;

CREATE TABLE IF NOT EXISTS `store_print_profiles` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `tenant_id` INT NOT NULL,
  `name` VARCHAR(64) NOT NULL COMMENT '打印机名称',
  `brand` VARCHAR(32) NOT NULL COMMENT 'local_label/xprinter_cloud_label/feie_label/yilian_k4',
  `cloud_sn` VARCHAR(64) NULL COMMENT '云打印机 SN 或终端号',
  `cloud_device_key` VARCHAR(128) NULL COMMENT '飞鹅 KEY / 易联云 msign',
  `paper_preset` VARCHAR(32) NOT NULL DEFAULT 'custom',
  `paper_width_mm` INT NOT NULL DEFAULT 80,
  `paper_height_mm` INT NOT NULL DEFAULT 60,
  `local_printer_name_hint` VARCHAR(128) NULL COMMENT '本地 Windows 打印机名称提示',
  `margin_top_mm` INT NOT NULL DEFAULT 2,
  `margin_left_mm` INT NOT NULL DEFAULT 2,
  `is_default` TINYINT(1) NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_spp_store` (`store_id`),
  KEY `idx_spp_tenant` (`tenant_id`),
  CONSTRAINT `fk_spp_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_spp_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店打印机配置';

CREATE TABLE IF NOT EXISTS `store_print_scene_settings` (
  `store_id` BIGINT UNSIGNED NOT NULL,
  `scene` VARCHAR(32) NOT NULL COMMENT 'delivery_sheet / store_retail',
  `profile_id` BIGINT UNSIGNED NULL,
  `template_key` VARCHAR(64) NOT NULL DEFAULT 'delivery_meal_full',
  `copies_mode` VARCHAR(16) NOT NULL DEFAULT 'per_unit' COMMENT 'per_unit / per_order',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`store_id`, `scene`),
  KEY `idx_spss_profile` (`profile_id`),
  CONSTRAINT `fk_spss_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_spss_profile` FOREIGN KEY (`profile_id`) REFERENCES `store_print_profiles` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店打印场景绑定';

CREATE TABLE IF NOT EXISTS `store_print_jobs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `tenant_id` INT NOT NULL,
  `scene` VARCHAR(32) NOT NULL,
  `profile_id` BIGINT UNSIGNED NULL,
  `template_key` VARCHAR(64) NOT NULL,
  `brand` VARCHAR(32) NOT NULL,
  `cloud_sn` VARCHAR(64) NULL,
  `item_count` INT NOT NULL DEFAULT 0,
  `status` VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/success/failed/pending_local',
  `provider_order_id` VARCHAR(64) NULL,
  `error_msg` VARCHAR(512) NULL,
  `created_by_admin` VARCHAR(64) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_spj_store_created` (`store_id`, `created_at`),
  CONSTRAINT `fk_spj_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店打印任务日志';

-- 历史默认模板升级为推荐备餐面单
UPDATE `store_print_scene_settings`
SET `template_key` = 'delivery_meal_full'
WHERE `scene` = 'delivery_sheet' AND `template_key` = 'delivery_standard';
