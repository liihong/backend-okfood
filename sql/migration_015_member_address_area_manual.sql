-- 默认配送地址：手工指定片区后，后台改地址仅更新坐标，不再用地图重算片区
SET NAMES utf8mb4;

ALTER TABLE `member_addresses`
  ADD COLUMN `area_manual` TINYINT(1) NOT NULL DEFAULT 0
    COMMENT '1=片区由后台手工指定，管理端改详细地址时不再按坐标重算片区'
    AFTER `area`;
