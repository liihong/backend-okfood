-- 会员地址：独立存储省 / 市 / 区（逆地理或与小程序对齐）

ALTER TABLE `member_addresses`
  ADD COLUMN `province` VARCHAR(64) NULL COMMENT '省' AFTER `lat`,
  ADD COLUMN `city` VARCHAR(64) NULL COMMENT '市' AFTER `province`,
  ADD COLUMN `district` VARCHAR(64) NULL COMMENT '区' AFTER `city`;
