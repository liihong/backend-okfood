<template>
  <view class="page">
    <OkNavbar show-back title="请假管理 👌" />
    <scroll-view
      scroll-y
      class="scroll"
      :style="scrollStyle"
      refresher-enabled
      :refresher-triggered="refresherTriggered"
      @refresherrefresh="onLeaveRefresherRefresh"
    >
      <view class="page-leave">
        <view v-if="leaveRefreshing" class="leave-sync-hint">
          <text class="leave-sync-hint__text">正在同步最新状态…</text>
        </view>
        <view v-if="sfSelfServiceLocked" class="leave-block leave-block--deadline">
          <text class="leave-h3">配送进行中</text>
          <text class="leave-deadline-copy">
            当日配送已向顺丰推单，配送全部完成前无法自助修改请假，如需调整请联系客服 👌
          </text>
        </view>
        <view v-if="isOnLeaveNow && !sfSelfServiceLocked" class="leave-block leave-block--active">
          <text class="leave-status-tag">请假中</text>
          <text class="leave-h3 leave-h3--compact">{{ activeLeaveTitle }}</text>
          <text v-if="isRangeOnlyLeave" class="leave-range-line">{{ serverLeaveStart }} 至 {{ serverLeaveEnd }}</text>
          <text class="leave-range-hint">{{ activeLeaveHint }}</text>
          <button class="btn-cancel-leave" @click="confirmCancelAllLeave">取消请假</button>
        </view>
        <view
          v-if="!isOnLeaveNow && !isLeavePastDeadline && !sfSelfServiceLocked"
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
          v-if="!isOnLeaveNow && !isLeavePastDeadline && !sfSelfServiceLocked"
          class="leave-block"
        >
          <text class="leave-h3">多天请假 (出差/旅游等)</text>
          <text class="leave-tip leave-tip--range">* 须在每日 {{ formatDeadlineHint(leaveDeadlineTime) }} 前提交，与上方快速请假相同 👌</text>
          <view class="date-group">
            <view class="date-item" @click="openRangeDatePick('start')">
              <text class="date-label">开始日期</text>
              <text class="date-val">{{ rangeStart || '年 / 月 / 日' }}</text>
            </view>
            <view class="date-item" @click="openRangeDatePick('end')">
              <text class="date-label">结束日期</text>
              <text class="date-val">{{ rangeEnd || '年 / 月 / 日' }}</text>
            </view>
            <button class="btn-submit-range" @click="submitRange">提交多天计划</button>
          </view>
        </view>
        <view
          v-if="!isOnLeaveNow && isLeavePastDeadline && !sfSelfServiceLocked"
          class="leave-block leave-block--deadline"
        >
          <text class="leave-h3">今日已截止</text>
          <text class="leave-deadline-copy">
            已超过当日请假时间（ {{ formatDeadlineHint(leaveDeadlineTime) }} 前可提交新请假）。明日 0:00 起可再次操作 👌
          </text>
        </view>
      </view>
    </scroll-view>

    <!-- 原生 picker 在最小日期前仍会露出相邻行；用 picker-view 只渲染合法日期 -->
    <view v-if="rangePickKind" class="range-pick-mask" @click.self="closeRangeDatePick">
      <view class="range-pick-sheet" @click.stop>
        <view class="range-pick-bar">
          <text class="range-pick-bar__btn range-pick-bar__btn--cancel" @click="closeRangeDatePick">取消</text>
          <text class="range-pick-bar__title">{{ rangePickKind === 'start' ? '开始日期' : '结束日期' }}</text>
          <text class="range-pick-bar__btn range-pick-bar__btn--ok" @click="confirmRangeDatePick">确定</text>
        </view>
        <picker-view
          v-if="rangePickReady"
          :key="rangePickSession"
          class="range-pick-view"
          :value="pvValue"
          indicator-style="height: 72rpx"
          @change="onRangePickerViewChange"
        >
          <picker-view-column>
            <view v-for="y in yearOpts" :key="'y' + y" class="range-pick-cell">{{ y }}年</view>
          </picker-view-column>
          <picker-view-column>
            <view v-for="m in monthOpts" :key="'m' + m" class="range-pick-cell">{{ m }}月</view>
          </picker-view-column>
          <picker-view-column>
            <view v-for="d in dayOpts" :key="'d' + d" class="range-pick-cell">{{ d }}日</view>
          </picker-view-column>
        </picker-view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getNavbarLayout } from '@/utils/navbar.js'
import { request, clearMemberSession, isUserMeNotFoundError } from '@/utils/api.js'
import { ymdTodayShanghai, addDaysIso } from '@/utils/memberDeliveryDate.js'

const isTomorrowLeave = ref(false)
const rangeStart = ref('')
const rangeEnd = ref('')
/** 服务端区间请假快照（与「我的」页「请假中」口径一致：闭区间含上海今日） */
const serverLeaveStart = ref('')
const serverLeaveEnd = ref('')
/** 仅明日请假：不配送目标业务日（上海），与后端 tomorrow_leave_target_date 一致 */
const tomorrowTargetYmd = ref('')
const scrollStyle = ref({})
/** 后台拉取 /me 时顶部轻提示，不遮挡操作 */
const leaveRefreshing = ref(false)
/** 并发 sync 序号，只应用最后一次结果，避免乱序覆盖 */
let leaveSyncGeneration = 0
/** 防重复提交（快速请假 / 区间 / 取消） */
const leaveActionBusy = ref(false)
/** scroll-view 下拉刷新动画状态 */
const refresherTriggered = ref(false)
/** 与后台 app_settings.leave_deadline_time 一致，默认 21:00:00 */
const leaveDeadlineTime = ref('21:00:00')
const sfSelfServiceLocked = ref(false)

/**
 * 请假页专用：拉取 /api/user/me。
 * 部分机型/弱网下 uni.request 可能长时间不回调；单独缩短 timeout 并配合 race 硬截止，避免「一直正在同步」。
 */
const LEAVE_ME_SYNC_MS = 20000
/** 多天请假可选的最远日期（相对「明天」） */
const RANGE_PICK_DAYS_MAX = 730

/** 自定义日期弹层：picker-view 列中不含最小日之前的项 */
const rangePickKind = ref(null)
const rangePickLo = ref('')
const rangePickHi = ref('')
const yearOpts = ref([])
const monthOpts = ref([])
const dayOpts = ref([])
const pvValue = ref([0, 0, 0])
/** 安卓 picker-view 须等列数据就绪后再挂载，否则 column 高度为 0 */
const rangePickReady = ref(false)
const rangePickSession = ref(0)

function shanghaiTomorrowYmd() {
  return addDaysIso(ymdTodayShanghai(), 1)
}

function isValidYmd(ymd) {
  const { y, m, d } = ymdParts(ymd)
  return y >= 2000 && m >= 1 && m <= 12 && d >= 1 && d <= 31
}

function ymdParts(ymd) {
  const raw = String(ymd || '').slice(0, 10)
  const [ys, ms, ds] = raw.split('-')
  const y = Number(ys)
  const m = Number(ms)
  const d = Number(ds)
  return { y, m, d }
}

function ymdStr(y, m, d) {
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function daysInMonth(y, m) {
  return new Date(y, m, 0).getDate()
}

function clampYmdToRange(ymd, lo, hi) {
  if (!ymd || ymd < lo) return lo
  if (ymd > hi) return hi
  return ymd
}

function applyPickerState(lo, hi, ymdIn) {
  let ymd = clampYmdToRange(ymdIn, lo, hi)
  let { y, m, d } = ymdParts(ymd)
  const dim = daysInMonth(y, m)
  if (d > dim) d = dim
  ymd = clampYmdToRange(ymdStr(y, m, d), lo, hi)
  ;({ y, m, d } = ymdParts(ymd))

  const loP = ymdParts(lo)
  const hiP = ymdParts(hi)
  const years = []
  for (let yy = loP.y; yy <= hiP.y; yy++) years.push(yy)
  yearOpts.value = years

  let mLow = 1
  let mHigh = 12
  if (y === loP.y) mLow = loP.m
  if (y === hiP.y) mHigh = hiP.m
  const months = []
  for (let mm = mLow; mm <= mHigh; mm++) months.push(mm)
  monthOpts.value = months
  if (m < mLow) m = mLow
  if (m > mHigh) m = mHigh

  let dLow = 1
  let dHigh = daysInMonth(y, m)
  if (y === loP.y && m === loP.m) dLow = loP.d
  if (y === hiP.y && m === hiP.m) dHigh = Math.min(dHigh, hiP.d)
  const days = []
  for (let dd = dLow; dd <= dHigh; dd++) days.push(dd)
  dayOpts.value = days
  if (d < dLow) d = dLow
  if (d > dHigh) d = dHigh

  const iy = years.indexOf(y)
  const im = months.indexOf(m)
  const id = days.indexOf(d)
  pvValue.value = [Math.max(0, iy), Math.max(0, im), Math.max(0, id)]
}

function openRangeDatePick(kind) {
  const loGlobal = rangePickerMinYmd.value
  const hiGlobal = addDaysIso(loGlobal, RANGE_PICK_DAYS_MAX)
  const lo = kind === 'end' ? rangeEndPickerMinYmd.value : loGlobal
  const hi = hiGlobal
  if (!isValidYmd(lo) || !isValidYmd(hi) || lo > hi) {
    uni.showToast({ title: '日期加载失败，请重试', icon: 'none' })
    return
  }
  rangePickLo.value = lo
  rangePickHi.value = hi
  const raw = kind === 'start' ? rangeStart.value : rangeEnd.value
  const cur = raw && raw >= lo && raw <= hi ? raw : lo
  applyPickerState(lo, hi, cur)
  if (!yearOpts.value.length || !monthOpts.value.length || !dayOpts.value.length) {
    uni.showToast({ title: '日期加载失败，请重试', icon: 'none' })
    return
  }
  rangePickReady.value = false
  rangePickKind.value = kind
  rangePickSession.value += 1
  nextTick(() => {
    if (rangePickKind.value !== kind) return
    rangePickReady.value = true
    nextTick(() => {
      if (rangePickKind.value !== kind) return
      applyPickerState(lo, hi, cur)
    })
  })
}

function closeRangeDatePick() {
  rangePickKind.value = null
  rangePickReady.value = false
}

function onRangePickerViewChange(e) {
  const lo = rangePickLo.value
  const hi = rangePickHi.value
  const [iyRaw, imRaw, idRaw] = (e.detail.value || [0, 0, 0]).map(Number)
  const years = yearOpts.value
  const y = years[Math.min(Math.max(0, iyRaw), years.length - 1)]
  const loP = ymdParts(lo)
  const hiP = ymdParts(hi)
  let mLow = 1
  let mHigh = 12
  if (y === loP.y) mLow = loP.m
  if (y === hiP.y) mHigh = hiP.m
  const tempMonths = []
  for (let mm = mLow; mm <= mHigh; mm++) tempMonths.push(mm)
  const m = tempMonths[Math.min(Math.max(0, imRaw), tempMonths.length - 1)]
  let dLow = 1
  let dHigh = daysInMonth(y, m)
  if (y === loP.y && m === loP.m) dLow = loP.d
  if (y === hiP.y && m === hiP.m) dHigh = Math.min(dHigh, hiP.d)
  const span = Math.max(0, dHigh - dLow)
  const d = dLow + Math.min(Math.max(0, idRaw), span)
  applyPickerState(lo, hi, ymdStr(y, m, d))
}

function confirmRangeDatePick() {
  const y = yearOpts.value[pvValue.value[0]]
  const m = monthOpts.value[pvValue.value[1]]
  const d = dayOpts.value[pvValue.value[2]]
  if (y == null || m == null || d == null) {
    closeRangeDatePick()
    return
  }
  const ymd = ymdStr(y, m, d)
  const lo = rangePickLo.value
  const hi = rangePickHi.value
  const v = clampYmdToRange(ymd, lo, hi)
  if (rangePickKind.value === 'start') {
    rangeStart.value = v
    if (rangeEnd.value && rangeEnd.value < v) rangeEnd.value = v
  } else {
    rangeEnd.value = v
  }
  closeRangeDatePick()
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

/** 与后端 is_leave_deadline_passed 一致：当前上海时刻严格晚于截止时刻（仅用于展示；提交前须再调一次） */
function isLeavePastDeadlineNow() {
  return shanghaiSecondsSinceMidnight() > parseDeadlineToSeconds(leaveDeadlineTime.value)
}

/** 展示用：因未用定时器，长时间停留可能不会自动切换为「已截止」，以提交时校验与后端为准 */
const isLeavePastDeadline = computed(() => isLeavePastDeadlineNow())

function formatDeadlineHint(t) {
  const s = String(t || '21:00:00')
  const m = s.match(/^(\d{1,2}):(\d{2})/)
  return m ? `${m[1]}:${m[2]}` : '21:00'
}

const isRangeOnlyLeave = computed(
  () => Boolean(serverLeaveStart.value && serverLeaveEnd.value),
)

/** 多天请假：可选日期从上海「明天」起，当日及更早不在选择器中展示 */
const rangePickerMinYmd = computed(() => shanghaiTomorrowYmd())

/** 结束日不得早于开始日，且不得早于「明天」 */
const rangeEndPickerMinYmd = computed(() => {
  const min = rangePickerMinYmd.value
  const rs = rangeStart.value
  return rs && rs >= min ? rs : min
})

const activeLeaveTitle = computed(() => {
  if (isRangeOnlyLeave.value) return '当前区间请假'
  if (isTomorrowLeave.value) {
    const md = ymdToDotMd(tomorrowTargetYmd.value)
    return md ? `${md} 请假` : '请假中'
  }
  return '当前请假'
})

const activeLeaveHint = computed(() => {
  if (isRangeOnlyLeave.value) {
    const end = serverLeaveEnd.value
    return end ? `${end}日24：00结束请假` : ''
  }
  if (isTomorrowLeave.value) {
    return '到明日24：00结束请假'
  }
  return ''
})

function ymdFromApi(d) {
  if (d == null || d === '') return ''
  const s = String(d)
  return s.length >= 10 ? s.slice(0, 10) : s
}

/** 展示用：月.日，与「我的」页一致 */
function ymdToDotMd(ymd) {
  const raw = ymdFromApi(ymd)
  if (!raw) return ''
  const parts = raw.split('-')
  if (parts.length < 3) return ''
  const m = Number(parts[1])
  const d = Number(parts[2])
  if (!m || !d) return ''
  return `${m}.${d}`
}

/**
 * @param {{ noBanner?: boolean }} [opts] noBanner：下拉刷新时不再显示顶部黄条，避免与 refresher 重复
 */
async function syncLeaveFromServer(opts = {}) {
  const noBanner = Boolean(opts.noBanner)
  const gen = ++leaveSyncGeneration
  if (!noBanner) leaveRefreshing.value = true
  try {
    const me = await Promise.race([
      request('/api/user/me', { method: 'GET', timeout: LEAVE_ME_SYNC_MS }),
      new Promise((_, reject) => {
        setTimeout(() => {
          reject(new Error('网络异常，同步超时，请稍后重试'))
        }, LEAVE_ME_SYNC_MS + 2000)
      }),
    ])
    if (gen !== leaveSyncGeneration) return
    if (me?.leave_deadline_time) {
      leaveDeadlineTime.value = String(me.leave_deadline_time).trim()
    }
    sfSelfServiceLocked.value = Boolean(me?.sf_self_service_locked)
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
    if (gen !== leaveSyncGeneration) return
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
  } finally {
    if (gen === leaveSyncGeneration && !noBanner) {
      leaveRefreshing.value = false
    }
  }
}

/** 列表区域下拉刷新：与 onShow 同源拉取 /me */
async function onLeaveRefresherRefresh() {
  refresherTriggered.value = true
  try {
    await syncLeaveFromServer({ noBanner: true })
  } finally {
    refresherTriggered.value = false
  }
}

function confirmCancelAllLeave() {
  uni.showModal({
    title: '取消请假',
    content:
      '将清除当前区间请假及「明天请假」标记，确定取消？\n若当日配送已向顺丰推单，将无法自助取消，请联系客服。',
    success: async (res) => {
      if (!res.confirm) return
      if (leaveActionBusy.value) return
      leaveActionBusy.value = true
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
      } finally {
        leaveActionBusy.value = false
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
  if (leaveActionBusy.value) return
  const wasTomorrow = isTomorrowLeave.value
  if (!wasTomorrow && isLeavePastDeadlineNow()) {
    uni.showToast({
      title: `已超过当日请假时间（${formatDeadlineHint(leaveDeadlineTime.value)} 前可提交）`,
      icon: 'none',
    })
    return
  }
  leaveActionBusy.value = true
  try {
    if (wasTomorrow) {
      await request('/api/user/leave', {
        method: 'POST',
        data: { type: 'clear_tomorrow' },
      })
      await syncLeaveFromServer()
      uni.showToast({ title: '已取消明天请假', icon: 'success' })
    } else {
      await request('/api/user/leave', {
        method: 'POST',
        data: { type: 'tomorrow' },
      })
      await syncLeaveFromServer()
      uni.showToast({ title: '已提交明天请假', icon: 'success' })
    }
  } catch (e) {
    uni.showToast({
      title: e instanceof Error ? e.message : wasTomorrow ? '取消失败' : '提交失败',
      icon: 'none',
    })
  } finally {
    leaveActionBusy.value = false
  }
}

async function submitRange() {
  if (leaveActionBusy.value) return
  if (isLeavePastDeadlineNow()) {
    uni.showToast({
      title: `已超过当日请假时间（${formatDeadlineHint(leaveDeadlineTime.value)} 前可提交）`,
      icon: 'none',
    })
    return
  }
  if (!rangeStart.value || !rangeEnd.value) {
    uni.showToast({ title: '请选择起止日期', icon: 'none' })
    return
  }
  if (rangeStart.value > rangeEnd.value) {
    uni.showToast({ title: '开始日期不能晚于结束日期', icon: 'none' })
    return
  }
  const minDay = shanghaiTomorrowYmd()
  if (rangeStart.value < minDay || rangeEnd.value < minDay) {
    uni.showToast({ title: '多天请假须从明天起选日期', icon: 'none' })
    return
  }
  leaveActionBusy.value = true
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
  } finally {
    leaveActionBusy.value = false
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

.leave-sync-hint {
  padding: 20rpx 28rpx;
  margin-bottom: 24rpx;
  background: rgba(250, 204, 21, 0.2);
  border-radius: 24rpx;
  border: 1px solid rgba(250, 204, 21, 0.45);
}

.leave-sync-hint__text {
  font-size: 24rpx;
  color: $ok-slate-600;
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

.range-pick-mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 10000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.range-pick-sheet {
  background: #fff;
  border-radius: 32rpx 32rpx 0 0;
  padding-bottom: env(safe-area-inset-bottom);
}

.range-pick-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 32rpx;
  border-bottom: 1px solid $ok-slate-100;
}

.range-pick-bar__title {
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-slate-600;
}

.range-pick-bar__btn {
  font-size: 30rpx;
  font-weight: 800;
  padding: 12rpx 20rpx;
}

.range-pick-bar__btn--cancel {
  color: $ok-slate-400;
}

.range-pick-bar__btn--ok {
  color: $ok-forest-green;
}

.range-pick-view {
  width: 100%;
  height: 440rpx;
}

.range-pick-cell {
  height: 72rpx;
  line-height: 72rpx;
  text-align: center;
  font-size: 32rpx;
  font-weight: 800;
  color: $ok-slate-800;
}
</style>
