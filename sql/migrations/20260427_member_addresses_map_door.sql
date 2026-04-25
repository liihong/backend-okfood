-- 用户地址：拆分「地图/地区选点」与「门牌详细」；完整串仍存 detail_address
ALTER TABLE `member_addresses`
  ADD COLUMN `map_location_text` VARCHAR(500) NULL
    COMMENT '地图选点/省市区道路小区等收货位置文字'
    AFTER `detail_address`,
  ADD COLUMN `door_detail` VARCHAR(500) NULL
    COMMENT '楼栋、单元、门牌等补充地址'
    AFTER `map_location_text`;
