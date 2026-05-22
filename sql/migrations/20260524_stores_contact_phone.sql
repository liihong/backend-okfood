-- 门店配置：商家联系电话（小程序订单详情「联系商家」拨打）
ALTER TABLE `stores`
  ADD COLUMN `store_contact_phone` VARCHAR(20) NULL COMMENT '商家联系电话，小程序联系商家拨打' AFTER `store_lat`;
