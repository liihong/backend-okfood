"""餐段常量：午餐为默认口径，与现网行为一致。"""

from app.models.enums import DeliverySheetView, MealPeriod

# 经典周/月/次卡（无模版）入账时的默认餐段快照
DEFAULT_MEAL_PERIODS_SNAPSHOT: list[str] = [MealPeriod.LUNCH.value]

# 大表/推单/快照默认餐段（午餐链路不传参时等价于此）
DEFAULT_MEAL_PERIOD = MealPeriod.LUNCH.value

SHEET_VIEW_LUNCH = DeliverySheetView.LUNCH.value
SHEET_VIEW_DINNER = DeliverySheetView.DINNER.value
SHEET_VIEW_LUNCH_DINNER = DeliverySheetView.LUNCH_DINNER.value
