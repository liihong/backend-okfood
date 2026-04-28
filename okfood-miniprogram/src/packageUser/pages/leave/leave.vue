<template>
  <view class="page">
    <OkNavbar show-back title="请假管理 👌" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle">
      <view v-if="leaveSyncing" class="page-leave page-leave--sync">
        <text class="leave-loading-text">正在同步请假状态…</text>
      </view>
      <view v-else class="page-leave">
        <view v-if="isOnLeaveNow" class="leave-block leave-block--active">
          <text class="leave-status-tag">请假中</text>
          <text class="leave-h3 leave-h3--compact">{{ activeLeaveTitle }}</text>
          <text class="leave-range-line">{{ leaveLineStart }} 至 {{ leaveLineEnd }}</text>
          <text class="leave-range-hint">{{ activeLeaveHint }}</text>
          <button class="btn-cancel-leave" @click="confirmCancelAllLeave">取消请假</button>
        </view>
        <view
          v-if="!isOnLeaveNow && !isLeavePastDeadline"
          class="leave-block"
        >
          <text class="leave-h3">明天有事 · 快速请假</text>
          <button
            class="btn-fast-leave"
            :class="{ active: isTomorrowLeave }"
            @click="toggleTomorrow"
          >
            {{ isTomorrowLeave ? '👌 明天已请假 (点击取消)' : '明天有事，点此请假' }}
          </button>
          <text class="leave-tip">* 每日 {{ formatDeadlineHint(leaveDeadlineTime) }} 前操作，餐次顺延 👌</text>
        </view>
        <view
          v-if="!isOnLeaveNow && !isLeavePastDeadline"
          class="leave-block"
        >
          <text class="leave-h3">多天请假 (出差/旅游等)</text>
          <text class="leave-tip leave-tip--range">* 须在每日 {{ formatDeadlineHint(leaveDeadlineTime) }} 前提交，与上方快速请假相同 👌</text>
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
        <view
          v-if="!isOnLeaveNow && isLeavePastDeadline"
          class="leave-block leave-block--deadline"
        >
          <text class="leave-h3">今日已截止</text>
          <text class="leave-deadline-copy">
            已超过当日请假时间（ {{ formatDeadlineHint(leaveDeadlineTime) }} 前可提交新请假）。明日 0:00 起可再次操作 👌
          </text>
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
import { request, clearMemberSession, isUserMeNotFoundError } from '@/utils/api.js'

const isTomorrowLeave = ref(false)
const rangeStart = ref('')
const rangeEnd = ref('')
/** 服务端区间请假快照（与「我的」页「请假中」口径一致：闭区间含上海今日） */
const serverLeaveStart = ref('')
const serverLeaveEnd = ref('')
/** 仅明日请假：不配送目标业务日（上海），与后端 tomorrow_leave_target_date 一致 */
const tomorrowTargetYmd = ref('')
const scrollStyle = ref({})
const leaveSyncing = ref(true)
/** 与后台 app_settings.leave_deadline_time 一致，默认 21:00:00 */
const leaveDeadlineTime = ref('21:00:00')

/**
 * 请假页专用：拉取 /api/user/me。
 * 部分机型/弱网下 uni.request 可能长时间不回调；单独缩短 timeout 并配合 race 硬截止，避免「一直正在同步」。
 */
const LEAVE_ME_SYNC_MS = 20000

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

function shanghaiTomorrowYmd() {
  return addDaysYmdShanghai(shanghaiTodayYmd(), 1)
}

/** 在「上海日」上增减天数，返回 en-CA yyyy-mm-dd */
function addDaysYmdShanghai(ymd, deltaDays) {
  if (!ymd) return ''
  const t = new Date(`${ymd}T12:00:00+08:00`)
  const t2 = new Date(t.getTime() + deltaDays * 24 * 60 * 60 * 1000)
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(t2)
  const y = parts.find((p) => p.type === 'year')?.value
  const m = parts.find((p) => p.type === 'month')?.value
  const d = parts.find((p) => p.type === 'day')?.value
  if (y && m && d) return `${y}-${m}-${d}`
  return ymd
}

/** 已有「明天请假」或已设置区间（含尚未开始的未来区间）：只展示状态与取消，不展示新提交入口 */
const isOnLeaveNow = computed(() => {
  if (isTomorrowLeave.value) return true
  const s = serverLeaveStart.value
  const e = serverLeaveEnd.value
  return Boolean(s && e)
})

function shanghaiSecondsSinceMidnight() {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date())
  const hour = Number(parts.find((p) => p.type === 'hour')?.value)
  const minute = Number(parts.find((p) => p.type === 'minute')?.value)
  const second = Number(parts.find((p) => p.type === 'second')?.value)
  if (Number.isNaN(hour) || Number.isNaN(minute)) return 0
  return hour * 3600 + minute * 60 + (Number.isNaN(second) ? 0 : second)
}

function parseDeadlineToSeconds(str) {
  const s = String(str || '21:00:00').trim()
  const m = s.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?/)
  if (!m) return 21 * 3600
  return Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3] ?? 0)
}

/** 与后端 is_leave_deadline_passed 一致：当前上海时刻严格晚于截止时刻 */
const isLeavePastDeadline = computed(() => {
  return shanghaiSecondsSinceMidnight() > parseDeadlineToSeconds(leaveDeadlineTime.value)
})

function formatDeadlineHint(t) {
  const s = String(t || '21:00:00')
  const m = s.match(/^(\d{1,2}):(\d{2})/)
  return m ? `${m[1]}:${m[2]}` : '21:00'
}

const isRangeOnlyLeave = computed(
  () => Boolean(serverLeaveStart.value && serverLeaveEnd.value),
)

const activeLeaveTitle = computed(() => {
  if (isRangeOnlyLeave.value) return '当前区间请假'
  if (isTomorrowLeave.value) return '明日配送请假'
  return '当前请假'
})

const leaveLineStart = computed(() => {
  if (isRangeOnlyLeave.value) return serverLeaveStart.value
  if (isTomorrowLeave.value) {
    const t = tomorrowTargetYmd.value
    if (t) return addDaysYmdShanghai(t, -1)
    return shanghaiTodayYmd()
  }
  return serverLeaveStart.value
})

const leaveLineEnd = computed(() => {
  if (isRangeOnlyLeave.value) return serverLeaveEnd.value
  if (isTomorrowLeave.value) {
    return tomorrowTargetYmd.value || shanghaiTomorrowYmd()
  }
  return serverLeaveEnd.value
})

const activeLeaveHint = computed(() => {
  if (isRangeOnlyLeave.value) return '（与配送请假状态一致）'
  if (isTomorrowLeave.value) {
    return '（自提交当日起至目标日 24:00 止）'
  }
  return '（按以上日期；与配送请假状态一致）'
})

function ymdFromApi(d) {
  if (d == null || d === '') return ''
  const s = String(d)
  return s.length >= 10 ? s.slice(0, 10) : s
}

async function syncLeaveFromServer() {
  leaveSyncing.value = true
  try {
    const me = await Promise.race([
      request('/api/user/me', { method: 'GET', timeout: LEAVE_ME_SYNC_MS }),
      new Promise((_, reject) => {
        setTimeout(() => {
          reject(new Error('网络异常，同步超时，请稍后重试'))
        }, LEAVE_ME_SYNC_MS + 2000)
      }),
    ])
    if (me?.leave_deadline_time) {
      leaveDeadlineTime.value = String(me.leave_deadline_time).trim()
    }
    isTomorrowLeave.value = Boolean(me?.is_leaved_tomorrow)
    tomorrowTargetYmd.value = ymdFromApi(me?.tomorrow_leave_target_date)
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
  } catch (e) {
    if (isUserMeNotFoundError(e)) {
      clearMemberSession()
      uni.showToast({ title: '登录已失效，请重新登录', icon: 'none' })
      setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
    } else {
      const msg = e instanceof Error ? e.message : ''
      if (msg.includes('同步超时') || msg.includes('请求超时')) {
        uni.showToast({ title: msg, icon: 'none' })
      }
    }
    /* 其它错误：保持本地展示，避免普通失败也弹窗 */
  } finally {
    leaveSyncing.value = false
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
      await syncLeaveFromServer()
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
    await syncLeaveFromServer()
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
    uni.showToast({ title: '请假成功', icon: 'success' })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/mine/index' })
    }, 1000)
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

.page-leave--sync {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 40vh;
}

.leave-loading-text {
  font-size: 28rpx;
  color: $ok-slate-400;
  font-weight: 800;
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

.leave-block--deadline {
  border-color: $ok-slate-200;
  background: #fafafa;
}

.leave-deadline-copy {
  display: block;
  font-size: 28rpx;
  line-height: 1.55;
  color: $ok-slate-500;
  font-weight: 700;
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

.leave-tip--range {
  margin-top: 0;
  margin-bottom: 24rpx;
  text-align: left;
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
