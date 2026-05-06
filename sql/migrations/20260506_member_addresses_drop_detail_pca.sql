-- 移除 member_addresses 的 detail_address 与省市区独立列；仅保留 map_location_text + door_detail。
-- 须已存在 map_location_text / door_detail（见 20260427_member_addresses_map_door.sql）。
-- 若某列已删除，对应 ALTER 报错可忽略。

SET NAMES utf8mb4;

UPDATE `member_addresses`
SET `map_location_text` = TRIM(`detail_address`)
WHERE (`map_location_text` IS NULL OR TRIM(`map_location_text`) = '')
  AND `detail_address` IS NOT NULL
  AND TRIM(`detail_address`) <> '';

ALTER TABLE `member_addresses` DROP COLUMN `province`;
ALTER TABLE `member_addresses` DROP COLUMN `city`;
ALTER TABLE `member_addresses` DROP COLUMN `district`;
ALTER TABLE `member_addresses` DROP COLUMN `detail_address`;
