"""业务服务层 — 按端与域划分。

目录结构
--------
admin/      管理后台专用（dashboard、库存、财务、补偿等）
client/     小程序 / 用户端专用（首页、支付、零售单等）
delivery/   配送域（配送单、顺丰、骑手任务）
member/     会员域（资料、地址、请假、续费，admin + client 共用）
order/      订单域（单餐订单等）
shared/     基础设施（地图、门店配置、上传、租户集成）
meal_period/  餐段业务规则（午/晚分离）
dinner/       晚餐配送专项
douyin/       抖音对接
marketing/    营销 / 优惠券
sf_open/      顺丰开放平台 SDK
"""
