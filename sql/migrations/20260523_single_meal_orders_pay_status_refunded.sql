-- 单次点餐：支付状态需支持微信退款后的「已退款」（原为 ENUM 仅 未支付/已支付，会触发 Data truncated）
ALTER TABLE `single_meal_orders`
  MODIFY COLUMN `pay_status`
    ENUM('未支付', '已支付', '已退款')
    NOT NULL
    DEFAULT '未支付';
