-- 已移除短信验证码登录；删除历史表（若不存在可忽略报错）
DROP TABLE IF EXISTS `sms_verification`;
