-- 微信退款（secapi）商户 API 证书路径：按门店、租户覆盖，未填回退 .env
ALTER TABLE `stores`
    ADD COLUMN `wechat_pay_ssl_cert_path` VARCHAR(512) NULL DEFAULT NULL COMMENT '微信退款 apiclient_cert.pem 路径' AFTER `uu_open_app_key`,
    ADD COLUMN `wechat_pay_ssl_key_path` VARCHAR(512) NULL DEFAULT NULL COMMENT '微信退款 apiclient_key.pem 路径' AFTER `wechat_pay_ssl_cert_path`;

ALTER TABLE `tenant_integration_settings`
    ADD COLUMN `wechat_pay_ssl_cert_path` VARCHAR(512) NULL DEFAULT NULL COMMENT '租户默认证书 apiclient_cert.pem 路径' AFTER `wechat_pay_notify_url`,
    ADD COLUMN `wechat_pay_ssl_key_path` VARCHAR(512) NULL DEFAULT NULL COMMENT '租户默认证书 apiclient_key.pem 路径' AFTER `wechat_pay_ssl_cert_path`;
