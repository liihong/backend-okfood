-- 菜品库：辣度（会员端展示）、内部操作说明（仅管理端）
ALTER TABLE `menu_dish`
  ADD COLUMN `spice_level` VARCHAR(16) NULL DEFAULT NULL COMMENT '辣度代码：none/mild/medium/hot' AFTER `single_order_price_yuan`,
  ADD COLUMN `internal_view_sop` TEXT NULL COMMENT '内部查看操作说明，不对会员展示' AFTER `spice_level`;
