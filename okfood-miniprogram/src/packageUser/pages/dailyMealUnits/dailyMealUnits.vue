<template>
  <view class="page">
    <OkNavbar show-back title="每日送达份数" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="wrap">
        <view v-if="showMealPeriodTabs" class="period-tabs">
          <view
            class="period-tab"
            :class="{ 'period-tab--active': mealPeriod === 'lunch' }"
            @tap="switchMealPeriod('lunch')"
          >
            午餐
          </view>
          <view
            class="period-tab"
            :class="{ 'period-tab--active': mealPeriod === 'dinner' }"
            @tap="switchMealPeriod('dinner')"
          >
            晚餐
          </view>
        </view>

        <text class="lead">
          {{ periodLabel }}每个配送日需送达的份数；确认送达时按该份数从剩余次数中扣减。范围为 1～10 份。
        </text>

        <view v-if="sheetPushedToday" class="notice notice--info">
          <text class="notice-txt">
            今日{{ periodLabel }}配送大表已同步顺丰，修改将预约在下一配送日生效；今日仍为 {{ effectiveUnits }} 份。
          </text>
        </view>
        <view v-else class="notice notice--info">
          <text class="notice-txt">今日{{ periodLabel }}尚未向顺丰推单，保存后立即生效。</text>
        </view>

        <view v-if="hasPendingDiff" class="notice notice--warn">
          <text class="notice-txt">
            当前今日 {{ effectiveUnits }} 份，已预约改为 {{ pendingUnits }} 份（下一配送日起）。
          </text>
        </view>

        <view v-if="serverUnitsRaw > 10" class="notice">
          <text class="notice-txt">
            当前后台记录为 {{ serverUnitsRaw }} 份。本页最多可调至 10 份；若需更多请联系客服。
          </text>
        </view>

        <view class="card">
          <text class="card-label">{{ periodLabel }}每日送达份数</text>
          <view class="units-stepper">
            <button
              class="units-stepper-btn"
              :disabled="units <= MIN_U || loading || sfLocked"
              @click="bump(-1)"
            >
              -
            </button>
            <text class="units-stepper-value">{{ units }}</text>
            <button
              class="units-stepper-btn"
              :disabled="units >= MAX_U || loading || sfLocked"
              @click="bump(1)"
            >
              +
            </button>
          </view>
        </view>

        <button
          class="submit-btn"
          :loading="saving"
          :disabled="loading || !dirty || saving || sfLocked"
          @click="onSave"
        >
          保存
        </button>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getPageScrollStyle } from '@/utils/navbar.js'
import { request, getMemberToken, clearMemberSession, isUserMeNotFoundError } from '@/utils/api.js'
import { markMinePageNeedsRefresh } from '@/utils/minePageRefresh.js'
import { guardMemberDeliverySelfService } from '@/utils/memberSelfServiceGuard.js'
import { showOkAlert } from '@/utils/okAlert.js'
import {
  MEAL_PERIOD_LUNCH,
  hasDinnerEntitlement,
  mealPeriodLabel,
} from '@/utils/memberMealPeriod.js'
import {
  dailyMealUnitsEditorValueFromProfile,
  dailyMealUnitsSaveAlertFromProfile,
  effectiveDailyMealUnitsFromProfile,
  guardSfSelfServiceLocked,
  pendingDailyMealUnitsFromProfile,
} from '@/utils/memberDailyMealUnitsDisplay.js'

const MIN_U = 1
const MAX_U = 10

const scrollStyle = ref({})
const loading = ref(true)
const saving = ref(false)
const sfLocked = ref(false)
const sheetPushedToday = ref(false)
const effectiveUnits = ref(1)
const pendingUnits = ref(null)
const serverUnitsRaw = ref(1)
const baselineUnits = ref(1)
const units = ref(1)
const mealPeriod = ref(MEAL_PERIOD_LUNCH)
const memberProfileCache = ref(null)

const showMealPeriodTabs = computed(() => hasDinnerEntitlement(memberProfileCache.value))
const periodLabel = computed(() => (showMealPeriodTabs.value ? mealPeriodLabel(mealPeriod.value) : ''))

const hasPendingDiff = computed(
  () =>
    pendingUnits.value != null &&
    pendingUnits.value !== effectiveUnits.value,
)

const dirty = computed(() => !loading.value && units.value !== baselineUnits.value)

function clampUnits(n) {
  const x = Math.floor(Number(n) || 0)
  return Math.min(MAX_U, Math.max(MIN_U, x))
}

function bump(delta) {
  units.value = clampUnits(units.value + delta)
}

function applyProfileToForm(data) {
  const period = mealPeriod.value
  const rawField =
    period === MEAL_PERIOD_LUNCH ? data?.daily_meal_units : data?.dinner_daily_meal_units
  const raw = Math.floor(Number(rawField) || 0)
  const safeRaw = raw >= 1 && raw <= 50 ? raw : 1
  serverUnitsRaw.value = safeRaw
  effectiveUnits.value = effectiveDailyMealUnitsFromProfile(data, period)
  pendingUnits.value = pendingDailyMealUnitsFromProfile(data, period)
  sheetPushedToday.value =
    period === MEAL_PERIOD_LUNCH
      ? data?.delivery_sheet_pushed_today === true
      : data?.dinner_delivery_sheet_pushed_today === true
  sfLocked.value =
    period === MEAL_PERIOD_LUNCH
      ? data?.sf_self_service_locked === true
      : data?.dinner_sf_self_service_locked === true
  const editorVal = clampUnits(dailyMealUnitsEditorValueFromProfile(data, period))
  units.value = editorVal
  baselineUnits.value = editorVal
}

function switchMealPeriod(period) {
  if (mealPeriod.value === period) return
  mealPeriod.value = period
  if (memberProfileCache.value) applyProfileToForm(memberProfileCache.value)
}

async function loadMe() {
  if (!getMemberToken()) {
    loading.value = false
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 400)
    return
  }
  loading.value = true
  try {
    const data = await request('/api/user/me', { method: 'GET' })
    if (!guardMemberDeliverySelfService(data)) {
      setTimeout(() => uni.navigateBack(), 400)
      return
    }
    memberProfileCache.value = data
    if (!guardSfSelfServiceLocked(data, mealPeriod.value)) {
      setTimeout(() => uni.navigateBack(), 400)
      return
    }
    applyProfileToForm(data)
  } catch (e) {
    if (isUserMeNotFoundError(e)) {
      clearMemberSession()
    }
    const msg = e instanceof Error ? e.message : '加载失败'
    uni.showToast({ title: msg, icon: 'none' })
    setTimeout(() => uni.navigateBack(), 500)
  } finally {
    loading.value = false
  }
}

async function onSave() {
  if (!dirty.value || saving.value || sfLocked.value) return
  if (!getMemberToken()) {
    uni.showToast({ title: '登录已失效', icon: 'none' })
    return
  }
  saving.value = true
  try {
    const body =
      mealPeriod.value === MEAL_PERIOD_LUNCH
        ? { daily_meal_units: clampUnits(units.value) }
        : { dinner_daily_meal_units: clampUnits(units.value) }
    const data = await request('/api/user/profile', {
      method: 'PATCH',
      data: body,
    })
    memberProfileCache.value = data
    applyProfileToForm(data)
    markMinePageNeedsRefresh()
    const alertPayload = dailyMealUnitsSaveAlertFromProfile(data, mealPeriod.value)
    await showOkAlert({
      title: alertPayload.title,
      content: alertPayload.content,
      showCancel: false,
      confirmText: '确定',
      tone: 'success',
    })
    uni.navigateBack()
  } catch (err) {
    uni.showToast({ title: err?.message || '保存失败', icon: 'none', duration: 2800 })
  } finally {
    saving.value = false
  }
}

onShow(() => {
  scrollStyle.value = getPageScrollStyle()
  void loadMe()
})
</script>

<style lang="scss" scoped>
.page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: $ok-slate-50;
  box-sizing: border-box;
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
}

.wrap {
  padding: 32rpx 40rpx calc(48rpx + env(safe-area-inset-bottom));
}

.period-tabs {
  display: flex;
  flex-direction: row;
  gap: 16rpx;
  margin-bottom: 28rpx;
}

.period-tab {
  flex: 1;
  text-align: center;
  padding: 20rpx 0;
  border-radius: 999rpx;
  font-size: 28rpx;
  font-weight: 800;
  color: #64748b;
  background: #f1f5f9;
  border: 2rpx solid #e2e8f0;
}

.period-tab--active {
  color: #fff;
  background: $ok-forest-green;
  border-color: $ok-forest-green;
}

.lead {
  display: block;
  font-size: 28rpx;
  color: $ok-slate-600;
  font-weight: 700;
  line-height: 1.55;
  margin-bottom: 32rpx;
}

.notice {
  background: #fffbeb;
  border: 1rpx solid #fde68a;
  border-radius: 20rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 28rpx;
}

.notice--info {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.notice--warn {
  background: #fffbeb;
  border-color: #fde68a;
}

.notice--warn .notice-txt {
  color: #92400e;
}

.notice--info .notice-txt {
  color: #1e40af;
}

.notice-txt {
  font-size: 26rpx;
  font-weight: 700;
  color: #92400e;
  line-height: 1.45;
}

.card {
  background: #fff;
  border-radius: 32rpx;
  border: 1px solid $ok-slate-100;
  padding: 40rpx 36rpx 36rpx;
  margin-bottom: 40rpx;
}

.card-label {
  display: block;
  font-size: 28rpx;
  font-weight: 900;
  color: $ok-slate-800;
  margin-bottom: 28rpx;
}

.units-stepper {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 28rpx;
  padding: 8rpx 0 4rpx;
}

.units-stepper-btn {
  min-width: 88rpx;
  height: 88rpx;
  padding: 0;
  margin: 0;
  line-height: 86rpx;
  text-align: center;
  font-size: 40rpx;
  font-weight: 900;
  color: $ok-forest-green;
  background: #f1f5f9;
  border: 3rpx solid $ok-slate-100;
  border-radius: 20rpx;
  box-sizing: border-box;
}

.units-stepper-btn::after {
  border: none;
}

.units-stepper-btn[disabled] {
  opacity: 0.35;
  color: $ok-slate-500;
}

.units-stepper-value {
  min-width: 100rpx;
  text-align: center;
  font-size: 44rpx;
  font-weight: 950;
  color: $ok-slate-800;
  font-variant-numeric: tabular-nums;
}

.submit-btn {
  width: 100%;
  margin: 0;
  padding: 28rpx;
  font-size: 32rpx;
  font-weight: 900;
  color: #fff;
  background: $ok-forest-green;
  border: none;
  border-radius: 999rpx;
  line-height: 1.35;
}

.submit-btn::after {
  border: none;
}

.submit-btn[disabled] {
  opacity: 0.45;
}
</style>
