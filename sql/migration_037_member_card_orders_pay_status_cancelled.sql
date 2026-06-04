-- 开卡工单：支持「已取消」（会员自助取消未支付微信单）
-- 若线上 pay_status 仍为 ENUM('未缴','已缴')，本迁移会一并纳入「已退款」「已取消」。

ALTER TABLE `member_card_orders`
  MODIFY COLUMN `pay_status` VARCHAR(10) NOT NULL DEFAULT '未缴'
  COMMENT '未缴/已缴/已退款/已取消';
