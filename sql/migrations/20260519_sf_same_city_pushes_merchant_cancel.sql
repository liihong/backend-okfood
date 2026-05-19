-- 顺丰同城推单：管理端 cancelorder 成功后本地标记（监控页「创单状态」与回调状态乐观更新）
-- MySQL / MariaDB

ALTER TABLE `sf_same_city_pushes`
  ADD COLUMN `merchant_cancel_requested_at` DATETIME NULL
    COMMENT '管理端发起顺丰取消配送成功时间；回调到达后仍以顺丰推送刷新 sf_callback_order_status'
  AFTER `last_callback_kind`;
