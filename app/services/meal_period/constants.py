"""餐段常量：午餐为默认口径，与现网行为一致。"""

from app.models.enums import DeliverySheetView, MealPeriod

# 经典周/月/次卡（无模版）入账时的默认餐段快照
DEFAULT_MEAL_PERIODS_SNAPSHOT: list[str] = [MealPeriod.LUNCH.value]

# 大表/推单/快照/API 未传 meal_period 时的默认餐段（= 午餐，保持现网午餐链路不变）
# 注意：非法 meal_period 须走 normalize_meal_period 报错，禁止静默当成午餐
DEFAULT_MEAL_PERIOD = MealPeriod.LUNCH.value

SHEET_VIEW_LUNCH = DeliverySheetView.LUNCH.value
SHEET_VIEW_DINNER = DeliverySheetView.DINNER.value
SHEET_VIEW_LUNCH_DINNER = DeliverySheetView.LUNCH_DINNER.value
