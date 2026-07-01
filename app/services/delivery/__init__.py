"""配送域服务（管理后台 + 骑手端 + 顺丰回调共用）。

模块说明
--------
delivery_sheet_service              配送单构建与指标
delivery_sheet_meal_units_service   配送单餐份计算
delivery_sheet_push_snapshot_service 推单快照
delivery_sheet_units_backfill_service 餐份快照回填
delivery_day_lock_service           配送日锁定（推单后冻结）
courier_service                     骑手任务
courier_store_scope                 骑手门店范围
courier_task_sorting                任务排序
sf_same_city_service                顺丰同城推单
sf_order_fulfillment_service        顺丰订单履约
sf_callback_service                 顺丰回调处理
sf_open_notify_payload              回调载荷解析
"""
