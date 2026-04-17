<template>
  <view class="page">
    <OkNavbar show-back title="请假管理 👌" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle">
      <view class="page-leave">
        <view v-if="isOnLeaveNow" class="leave-block leave-block--active">
          <text class="leave-status-tag">请假中</text>
          <text class="leave-h3 leave-h3--compact">当前区间请假</text>
          <text class="leave-range-line">{{ serverLeaveStart }} 至 {{ serverLeaveEnd }}</text>
          <text class="leave-range-hint">（按上海日期；与配送请假状态一致）</text>
          <button class="btn-cancel-leave" @click="confirmCancelAllLeave">取消请假</button>
        </view>
        <view class="leave-block">
          <text class="leave-h3">明天有事 · 快速请假</text>
          <button
            class="btn-fast-leave"
            :class="{ active: isTomorrowLeave }"
            @click="toggleTomorrow"
          >
            {{ isTomorrowLeave ? '👌 明天已请假 (点击取消)' : '明天有事，点此请假' }}
          </button>
          <text class="leave-tip">* 每日 21:00 前操作，餐次顺延 👌</text>
        </view>
        <view class="leave-block">
          <text class="leave-h3">多天请假 (出差/旅游等)</text>
          <view class="date-group">
            <picker mode="date" :value="rangeStart" @change="onStart">
              <view class="date-item">
                <text class="date-label">开始日期</text>
                <text class="date-val">{{ rangeStart || '年 / 月 / 日' }}</text>
              </view>
            </picker>
            <picker mode="date" :value="rangeEnd" @change="onEnd">
              <view class="date-item">
                <text class="date-label">结束日期</text>
                <text class="date-val">{{ rangeEnd || '年 / 月 / 日' }}</text>
              </view>
            </picker>
            <button class="btn-submit-range" @click="submitRange">提交多天计划</button>
          </view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getNavbarLayout } from '@/utils/navbar.js'
import { request } from '@/utils/api.js'

const isTomorrowLeave = ref(false)
const rangeStart = ref('')
const rangeEnd = ref('')
/** 服务端区间请假快照（与「我的」页「请假中」口径一致：闭区间含上海今日） */
const serverLeaveStart = ref('')
const serverLeaveEnd = ref('')
const scrollStyle = ref({})

function shanghaiTodayYmd() {
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date())
    const y = parts.find((p) => p.type === 'year')?.value
    const m = parts.find((p) => p.type === 'month')?.value
    const d = parts.find((p) => p.type === 'day')?.value
    if (y && m && d) return `${y}-${m}-${d}`
  } catch {
    /* ignore */
  }
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

const isOnLeaveNow = computed(() => {
  const s = serverLeaveStart.value
  const e = serverLeaveEnd.value
  if (!s || !e) return false
  const today = shanghaiTodayYmd()
  return today >= s && today <= e
})

function ymdFromApi(d) {
  if (d == null || d === '') return ''
  const s = String(d)
  return s.length >= 10 ? s.slice(0, 10) : s
}

async function syncLeaveFromServer() {
  try {
    const me = await request('/api/user/me', { method: 'GET' })
    isTomorrowLeave.value = Boolean(me?.is_leaved_tomorrow)
    const lr = me?.leave_range
    if (lr && lr.start && lr.end) {
      const s = ymdFromApi(lr.start)
      const e = ymdFromApi(lr.end)
      serverLeaveStart.value = s
      serverLeaveEnd.value = e
      rangeStart.value = s
      rangeEnd.value = e
    } else {
      serverLeaveStart.value = ''
      serverLeaveEnd.value = ''
      rangeStart.value = ''
      rangeEnd.value = ''
    }
  } catch {
    /*未登录或网络失败时保持本地展示 */
  }
}

function confirmCancelAllLeave() {
  uni.showModal({
    title: '取消请假',
    content: '将清除当前区间请假及「明天请假」标记，确定取消？',
    success: async (res) => {
      if (!res.confirm) return
      try {
        await request('/api/user/leave', {
          method: 'POST',
          data: { type: 'cancel' },
        })
        await syncLeaveFromServer()
        uni.showToast({ title: '已取消请假', icon: 'success' })
      } catch (e) {
        uni.showToast({
          title: e instanceof Error ? e.message : '取消失败',
          icon: 'none',
        })
      }
    },
  })
}

onShow(() => {
  const { navBarTotal } = getNavbarLayout()
  scrollStyle.value = { height: `calc(100vh - ${navBarTotal}px)` }
  syncLeaveFromServer()
})

async function toggleTomorrow() {
  if (isTomorrowLeave.value) {
    try {
      await request('/api/user/leave', {
        method: 'POST',
        data: { type: 'clear_tomorrow' },
      })
      isTomorrowLeave.value = false
      uni.showToast({ title: '已取消明天请假', icon: 'success' })
    } catch (e) {
      uni.showToast({
        title: e instanceof Error ? e.message : '取消失败',
        icon: 'none',
      })
    }
    return
  }
  try {
    await request('/api/user/leave', {
      method: 'POST',
      data: {
        type: 'tomorrow',
      },
    })
    isTomorrowLeave.value = true
    uni.showToast({ title: '已提交明天请假', icon: 'success' })
  } catch (e) {
    uni.showToast({
      title: e instanceof Error ? e.message : '提交失败',
      icon: 'none',
    })
  }
}

function onStart(e) {
  rangeStart.value = e.detail.value
}
function onEnd(e) {
  rangeEnd.value = e.detail.value
}

async function submitRange() {
  if (!rangeStart.value || !rangeEnd.value) {
    uni.showToast({ title: '请选择起止日期', icon: 'none' })
    return
  }
  if (rangeStart.value > rangeEnd.value) {
    uni.showToast({ title: '开始日期不能晚于结束日期', icon: 'none' })
    return
  }
  try {
    await request('/api/user/leave', {
      method: 'POST',
      data: {
        type: 'range',
        start: rangeStart.value,
        end: rangeEnd.value,
      },
    })
    await syncLeaveFromServer()
    uni.showToast({ title: '已提交' })
    uni.navigateBack()
  } catch (e) {
    uni.showToast({
      title: e instanceof Error ? e.message : '提交失败',
      icon: 'none',
    })
  }
}
</script>

<style lang="scss" scoped>
.page {
  background: $ok-slate-50;
  min-height: 100vh;
}

.page-leave {
  padding: 40rpx;
  padding-bottom: 80rpx;
}

.leave-block {
  background: #fff;
  border-radius: 60rpx;
  padding: 50rpx;
  margin-bottom: 40rpx;
  border: 1px solid $ok-slate-100;
}

.leave-block--active {
  border-color: rgba(34, 197, 94, 0.35);
  background: linear-gradient(165deg, #f0fdf4 0%, #fff 55%);
}

.leave-status-tag {
  display: inline-block;
  font-size: 22rpx;
  font-weight: 950;
  color: #fff;
  background: $ok-forest-green;
  padding: 8rpx 24rpx;
  border-radius: 999rpx;
  margin-bottom: 24rpx;
}

.leave-h3--compact {
  margin-bottom: 16rpx;
}

.leave-range-line {
  display: block;
  font-size: 32rpx;
  font-weight: 950;
  color: $ok-forest-green;
  margin-bottom: 12rpx;
}

.leave-range-hint {
  display: block;
  font-size: 20rpx;
  color: $ok-slate-400;
  font-weight: 700;
  margin-bottom: 36rpx;
}

.btn-cancel-leave {
  width: 100%;
  padding: 32rpx;
  border-radius: 40rpx;
  font-weight: 950;
  border: 3rpx solid $ok-slate-200;
  background: #fff;
  color: $ok-slate-600;
  font-size: 28rpx;
}

.leave-h3 {
  display: block;
  font-size: 34rpx;
  font-weight: 950;
  color: #333;
  margin-bottom: 30rpx;
}

.btn-fast-leave {
  width: 100%;
  padding: 40rpx;
  border-radius: 40rpx;
  font-weight: 950;
  border: 5rpx solid $ok-urgent-red;
  background: #fff;
  color: $ok-urgent-red;
  font-size: 28rpx;
}

.btn-fast-leave.active {
  background: $ok-urgent-red;
  color: #fff;
  border-color: $ok-urgent-red;
  box-shadow: 0 20rpx 40rpx rgba(255, 62, 62, 0.2);
}

.leave-tip {
  display: block;
  font-size: 20rpx;
  color: #ccc;
  margin-top: 30rpx;
  text-align: center;
  font-weight: 800;
}

.date-group {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.date-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f7f8fa;
  padding: 30rpx 40rpx;
  border-radius: 30rpx;
}

.date-label {
  font-size: 24rpx;
  font-weight: 900;
  color: $ok-slate-400;
}

.date-val {
  font-size: 28rpx;
  font-weight: 950;
  color: $ok-forest-green;
}

.btn-submit-range {
  width: 100%;
  background: $ok-sunshine-yellow;
  color: $ok-forest-green;
  padding: 36rpx;
  border-radius: 60rpx;
  font-weight: 950;
  font-size: 32rpx;
  margin-top: 20rpx;
  border: none;
  box-shadow: 0 20rpx 40rpx rgba(250, 204, 21, 0.2);
}
</style>
