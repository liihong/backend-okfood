<template>
  <view class="page">
    <OkNavbar show-back title="每日送达份数" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="wrap">
        <text class="lead">
          每个配送日需送达的份数；骑手确认送达时按该份数从剩余次数中扣减。此处仅可通过加减调整，范围为
          1～10 份。
        </text>

        <view v-if="serverUnitsRaw > 10" class="notice">
          <text class="notice-txt">
            当前后台记录为 {{ serverUnitsRaw }} 份。本页最多可调至 10 份；若需更多请联系客服。
          </text>
        </view>

        <view class="card">
          <text class="card-label">每日送达份数</text>
          <view class="units-stepper">
            <button
              class="units-stepper-btn"
              :disabled="units <= MIN_U || loading"
              @click="bump(-1)"
            >
              -
            </button>
            <text class="units-stepper-value">{{ units }}</text>
            <button
              class="units-stepper-btn"
              :disabled="units >= MAX_U || loading"
              @click="bump(1)"
            >
              +
            </button>
          </view>
        </view>

        <button
          class="submit-btn"
          :loading="saving"
          :disabled="loading || !dirty || saving"
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
import { getNavbarLayout } from '@/utils/navbar.js'
import { request, getMemberToken, clearMemberSession, isUserMeNotFoundError } from '@/utils/api.js'

const MIN_U = 1
const MAX_U = 10

const scrollStyle = ref({})
const loading = ref(true)
const saving = ref(false)
/** 服务端原始值（未截断），用于大于 10 时的提示 */
const serverUnitsRaw = ref(1)
/** 进入本页时的可选范围内快照，用于判断是否修改 */
const baselineUnits = ref(1)
const units = ref(1)

const dirty = computed(() => !loading.value && units.value !== baselineUnits.value)

function clampUnits(n) {
  const x = Math.floor(Number(n) || 0)
  return Math.min(MAX_U, Math.max(MIN_U, x))
}

function bump(delta) {
  units.value = clampUnits(units.value + delta)
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
    const raw = Math.floor(Number(data?.daily_meal_units) || 0)
    const safeRaw = raw >= 1 && raw <= 50 ? raw : 1
    serverUnitsRaw.value = safeRaw
    const u = clampUnits(safeRaw)
    units.value = u
    baselineUnits.value = u
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
  if (!dirty.value || saving.value) return
  if (!getMemberToken()) {
    uni.showToast({ title: '登录已失效', icon: 'none' })
    return
  }
  saving.value = true
  try {
    await request('/api/user/profile', {
      method: 'PATCH',
      data: { daily_meal_units: clampUnits(units.value) },
    })
    baselineUnits.value = units.value
    uni.showToast({ title: '已保存', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 400)
  } catch (err) {
    uni.showToast({ title: err?.message || '保存失败', icon: 'none', duration: 2800 })
  } finally {
    saving.value = false
  }
}

onShow(() => {
  const { navBarTotal } = getNavbarLayout()
  scrollStyle.value = { height: `calc(100vh - ${navBarTotal}px)` }
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
