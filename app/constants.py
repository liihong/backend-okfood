"""业务常量（非枚举配置）。"""

# 地理编码失败或坐标不在任一配送区域内时使用，与 delivery_regions.name 无强制外键关联
UNASSIGNED_DELIVERY_AREA = "未分配"

# 短信/微信登录后自动建档占位；与真实登记冲突时由 register 覆盖为正式资料
STUB_MEMBER_NAME = "待完善"
STUB_MEMBER_ADDRESS = "待完善"
