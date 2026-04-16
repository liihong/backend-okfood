-- 业务说明：配送片区、坐标、展示地址以 member_addresses.is_default=1 为准。
-- members.address / lng / lat / area 由应用层逐步清空并不再用于业务逻辑；列保留便于历史数据与回滚。
-- 可选：将历史 address 迁入默认地址后执行 UPDATE members SET address='', lng=NULL, lat=NULL, area='未分配';

ALTER TABLE `members`
  MODIFY COLUMN `address` VARCHAR(500) NOT NULL DEFAULT '' COMMENT '已废弃：以 member_addresses 默认地址为准',
  MODIFY COLUMN `lng` DECIMAL(11,8) NULL COMMENT '已废弃：坐标在 member_addresses',
  MODIFY COLUMN `lat` DECIMAL(11,8) NULL COMMENT '已废弃：坐标在 member_addresses',
  MODIFY COLUMN `area` VARCHAR(64) NOT NULL DEFAULT '未分配' COMMENT '已废弃：片区以默认地址为准';
