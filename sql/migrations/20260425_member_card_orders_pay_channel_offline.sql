-- 小程序「已线下缴费」开卡登记：MemberCardOrder 使用 pay_channel = '线下'（见 CardPayChannel.OFFLINE）
ALTER TABLE `member_card_orders`
  MODIFY COLUMN `pay_channel` ENUM('微信','支付宝','线下') NOT NULL COMMENT '缴费渠道';
