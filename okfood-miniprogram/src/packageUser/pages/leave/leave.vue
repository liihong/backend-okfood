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
        <view v-if="showMealPeriodTabs" class="leave-period-tabs">
          <view
            class="leave-period-tab"
            :class="{ 'leave-period-tab--active': mealPeriod === 'lunch' }"
            @tap="switchMealPeriod('lunch')"
          >
            午餐
          </view>
          <view
            class="leave-period-tab"
            :class="{ 'leave-period-tab--active': mealPeriod === 'dinner' }"
            @tap="switchMealPeriod('dinner')"
          >
            晚餐
          </view>
        </view>
        <view v-if="leaveRefreshing" class="leave-sync-hint">
          <text class="leave-sync-hint__text">正在同步最新状态…</text>
        </view>
        <view v-if="showNewLeavePrepBlock" class="leave-block leave-block--deadline">
          <text class="leave-deadline-copy">{{ LEAVE_PREP_LOCKED_MSG }}</text>
        </view>
        <view v-if="isOnLeaveNow" class="leave-block leave-block--active">
          <text class="leave-status-tag">请假中</text>
          <text class="leave-h3 leave-h3--compact">{{ activeLeaveTitle }}</text>
          <text v-if="isRangeOnlyLeave" class="leave-range-line">{{ serverLeaveStart }} 至 {{ serverLeaveEnd }}</text>
          <text class="leave-range-hint">{{ activeLeaveHint }}</text>
          <view v-if="showActiveLeaveCancelLockHint" class="leave-prep-lock-hint">
            <text class="leave-deadline-copy">{{ LEAVE_PREP_CANCEL_LOCKED_HINT }}</text>
          </view>
          <button
            v-else-if="canCancelLeaveNow"
            class="btn-cancel-leave"
            :loading="leaveActionBusy"
            :disabled="leaveActionBusy"
            @tap="confirmCancelAllLeave"
          >
            取消请假
          </button>
        </view>
        <view v-if="memberCardBlocked && !isOnLeaveNow" class="leave-block leave-block--deadline">
          <text class="leave-deadline-copy">尚未开卡，无法提交请假。请先购买自律卡包并开通计划。</text>
        </view>
        <view v-if="!isOnLeaveNow && !leavePrepLocked && !memberCardBlocked" class="leave-block">
          <text class="leave-h3">明天有事 · 快速请假</text>
          <button
            class="btn-fast-leave"
            :class="{ active: isTomorrowLeave }"
            :loading="leaveActionBusy"
            :disabled="leaveActionBusy"
            @tap="toggleTomorrow"
          >
            {{ isTomorrowLeave ? '👌 明天已请假 (点击取消)' : '明天有事，点此请假' }}
          </button>
          <text class="leave-tip">* 供餐日当日 08:50 同步顺丰前可自助操作；推单配送完成前如需调整请联系客服 👌</text>
        </view>
        <view v-if="!isOnLeaveNow && !leavePrepLocked && !memberCardBlocked" class="leave-block">
          <text class="leave-h3">多天请假 (出差/旅游等)</text>
          <text class="leave-tip leave-tip--range">* 须从明天起选日期；供餐日 08:50 推顺丰后至配送完成前请联系客服 👌</text>
          <view class="date-group">
            <view class="date-item" @tap="openRangeDatePick('start')">
              <text class="date-label">开始日期</text>
              <text class="date-val">{{ rangeStart || '年 / 月 / 日' }}</text>
            </view>
            <view class="date-item" @tap="openRangeDatePick('end')">
              <text class="date-label">结束日期</text>
              <text class="date-val">{{ rangeEnd || '年 / 月 / 日' }}</text>
            </view>
            <button class="btn-submit-range" :loading="leaveActionBusy" :disabled="leaveActionBusy" @tap="submitRange">
              提交多天计划
            </button>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- 原生 picker 在最小日期前仍会露出相邻行；用 picker-view 只渲染合法日期 -->
    <view v-if="rangePickKind" class="range-pick-mask" @tap.self="closeRangeDatePick">
      <view class="range-pick-sheet" @tap.stop>
        <view class="range-pick-bar">
          <text class="range-pick-bar__btn range-pick-bar__btn--cancel" @tap="closeRangeDatePick">取消</text>
          <text class="range-pick-bar__title">{{ rangePickKind === 'start' ? '开始日期' : '结束日期' }}</text>
          <text class="range-pick-bar__btn range-pick-bar__btn--ok" @tap="confirmRangeDatePick">确定</text>
        </view>
        <view v-if="!rangePickReady" class="range-pick-placeholder">
          <text class="range-pick-placeholder__txt">正在加载日期…</text>
        </view>
        <picker-view
          v-if="rangePickReady"
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
import { showOkAlert } from '@/utils/okAlert.js'
import { getPageScrollStyle } from '@/utils/navbar.js'
import { request, clearMemberSession, isUserMeNotFoundError } from '@/utils/api.js'
import { markMinePageNeedsRefresh } from '@/utils/minePageRefresh.js'
import { ymdTodayShanghai, addDaysIso } from '@/utils/memberDeliveryDate.js'
import {
  isPaidCardAwaitingSetup,
  shouldPromptMemberCardPay,
} from '@/utils/memberProfile.js'
import { guardMemberDeliverySelfService } from '@/utils/memberSelfServiceGuard.js'
import {
  MEAL_PERIOD_LUNCH,
  MEAL_PERIOD_DINNER,
  hasDinnerEntitlement,
  leaveFieldsForPeriod,
  mealPeriodLabel,
} from '@/utils/memberMealPeriod.js'

const mealPeriod = ref(MEAL_PERIOD_LUNCH)
const memberProfileCache = ref(null)
const showMealPeriodTabs = computed(() => hasDinnerEntitlement(memberProfileCache.value))

function leavePostBody(extra = {}) {
  return { meal_period: mealPeriod.value, ...extra }
}

function applyLeaveFieldsFromProfile(me) {
  const f = leaveFieldsForPeriod(me, mealPeriod.value)
  isTomorrowLeave.value = Boolean(f.is_leaved_tomorrow)
  tomorrowTargetYmd.value = ymdFromApi(f.tomorrow_leave_target_date)
  const lr = f.leave_range
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
}

function switchMealPeriod(period) {
  if (mealPeriod.value === period) return
  mealPeriod.value = period
  if (memberProfileCache.value) applyLeaveFieldsFromProfile(memberProfileCache.value)
}

const activePeriodLabel = computed(() => mealPeriodLabel(mealPeriod.value))

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
/** 备餐锁窗：当日 21:00 起至次日 09:00，与后端 leave_prep_locked 一致 */
const leavePrepLocked = ref(false)
/** 未开卡：禁止新提交请假（若仍有历史请假记录则仅可取消） */
const memberCardBlocked = ref(false)
let leaveCardBlockRedirecting = false

/** 备餐锁窗内禁止新提交请假（与后端 guard 文案一致） */
const LEAVE_PREP_LOCKED_MSG = '您的菜品原材料已备好，不能请假，感谢理解和认可。'
/** 已在请假中、备餐锁窗内禁止自助取消（勿复用「不能请假」，避免与「请假中」矛盾） */
const LEAVE_PREP_CANCEL_LOCKED_HINT =
  '原材料备货中，暂不支持自助取消请假；到期将自动恢复，如需提前调整请联系客服 👌'

function toastLeavePrepLocked() {
  uni.showToast({ title: LEAVE_PREP_LOCKED_MSG, icon: 'none', duration: 3600 })
}

function toastLeaveCancelPrepLocked() {
  uni.showToast({ title: LEAVE_PREP_CANCEL_LOCKED_HINT, icon: 'none', duration: 3600 })
}

function applyMemberCardBlockFromMe(me) {
  const blocked =
    Boolean(me) &&
    typeof me === 'object' &&
    (shouldPromptMemberCardPay(me) || isPaidCardAwaitingSetup(me))
  memberCardBlocked.value = blocked
  return blocked
}

function redirectLeaveIfNoCardAndNotOnLeave(me) {
  if (!applyMemberCardBlockFromMe(me)) return
  if (isTomorrowLeave.value) return
  const s = serverLeaveStart.value
  const e = serverLeaveEnd.value
  if (s && e) return
  if (leaveCardBlockRedirecting) return
  leaveCardBlockRedirecting = true
  guardMemberDeliverySelfService(me)
  setTimeout(() => {
    uni.navigateBack({
      fail: () => uni.switchTab({ url: '/pages/mine/index' }),
    })
    leaveCardBlockRedirecting = false
  }, 300)
}

/**
 * 请假页专用：拉取 /api/user/me。
 * 部分机型/弱网下 uni.request 可能长时间不回调；单独缩短 timeout 并配合 race 硬截止，避免「一直正在同步」。
 */
const LEAVE_ME_SYNC_MS = 20000
/** 请假 POST 不必沿用全局 120s 超时；缩短后失败可重试，避免「像死机」 */
const LEAVE_POST_TIMEOUT_MS = 35000

function showLeaveMutationLoading(title) {
  try {
    uni.showLoading({
      title: title || '请稍候…',
      mask: true,
    })
  } catch {
    /* ignore */
  }
}

function hideLeaveMutationLoading() {
  try {
    uni.hideLoading()
  } catch {
    /* ignore */
  }
}

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
  const sessionAtOpen = Number(rangePickSession.value)

  /** 安卓部分机型单次 nextTick 后 picker-view 列仍为 0 高→空白：延迟挂载并二次对齐 */
  nextTick(() => {
    setTimeout(() => {
      if (rangePickKind.value !== kind || rangePickSession.value !== sessionAtOpen) return
      rangePickReady.value = true
      nextTick(() => {
        setTimeout(() => {
          if (rangePickKind.value !== kind || rangePickSession.value !== sessionAtOpen) return
          applyPickerState(lo, hi, cur)
          pvValue.value = [...pvValue.value]
        }, 48)
      })
    }, 72)
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

/** 仅未在请假中时展示「不能请假」独立提示块 */
const showNewLeavePrepBlock = computed(() => leavePrepLocked.value && !isOnLeaveNow.value)

/** 已在请假中且备餐锁窗：说明暂不可取消，而非「不能请假」 */
const showActiveLeaveCancelLockHint = computed(
  () => isOnLeaveNow.value && leavePrepLocked.value,
)

/** 请假中且非备餐锁窗：展示「取消请假」 */
const canCancelLeaveNow = computed(() => isOnLeaveNow.value && !leavePrepLocked.value)

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
  const prefix = showMealPeriodTabs.value ? `${activePeriodLabel.value} · ` : ''
  if (isRangeOnlyLeave.value) return `${prefix}当前区间请假`
  if (isTomorrowLeave.value) {
    const raw = ymdFromApi(tomorrowTargetYmd.value)
    const ymd = raw || addDaysIso(ymdTodayShanghai(), 1)
    const md = ymdToCnMd(ymd)
    return md ? `${prefix}${md} 请假` : `${prefix}明日请假`
  }
  return `${prefix}当前请假`
})

/** 请假结束提示：展示目标结束日 24:00，并说明到期自动恢复 */
function buildLeaveEndHint(ymd) {
  const md = ymdToCnMdHao(ymd)
  if (!md) return ''
  return `到${md}24：00结束请假。无需手动操作取消，请假状态会自动结束`
}

const activeLeaveHint = computed(() => {
  if (isRangeOnlyLeave.value) {
    return buildLeaveEndHint(serverLeaveEnd.value)
  }
  if (isTomorrowLeave.value) {
    const raw = ymdFromApi(tomorrowTargetYmd.value)
    const ymd = raw || addDaysIso(ymdTodayShanghai(), 1)
    return buildLeaveEndHint(ymd)
  }
  return ''
})

function ymdFromApi(d) {
  if (d == null || d === '') return ''
  const s = String(d)
  return s.length >= 10 ? s.slice(0, 10) : s
}

/** 展示用：如「5月28日」，与「我的」计划卡请假文案一致 */
function ymdToCnMd(ymd) {
  const raw = ymdFromApi(ymd)
  if (!raw) return ''
  const parts = raw.split('-')
  if (parts.length < 3) return ''
  const m = Number(parts[1])
  const d = Number(parts[2])
  if (!m || !d) return ''
  return `${m}月${d}日`
}

/** 展示用：如「5月28号」，用于请假结束时间提示 */
function ymdToCnMdHao(ymd) {
  const raw = ymdFromApi(ymd)
  if (!raw) return ''
  const parts = raw.split('-')
  if (parts.length < 3) return ''
  const m = Number(parts[1])
  const d = Number(parts[2])
  if (!m || !d) return ''
  return `${m}月${d}号`
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
    memberProfileCache.value = me
    leavePrepLocked.value = Boolean(me?.leave_prep_locked)
    applyLeaveFieldsFromProfile(me)
    redirectLeaveIfNoCardAndNotOnLeave(me)
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
  if (leavePrepLocked.value) {
    toastLeaveCancelPrepLocked()
    return
  }
  showOkAlert({
    title: '取消请假',
    content:
      '将清除当前区间请假及「明天请假」标记。今日仍不配送，自明日起恢复。确定取消？',
    success: async (res) => {
      if (!res.confirm) return
      if (leaveActionBusy.value) return
      leaveActionBusy.value = true
      showLeaveMutationLoading()
      try {
        await request('/api/user/leave', {
          method: 'POST',
          data: leavePostBody({ type: 'cancel' }),
          timeout: LEAVE_POST_TIMEOUT_MS,
        })
        await syncLeaveFromServer({ noBanner: true })
        markMinePageNeedsRefresh()
        uni.showToast({ title: '已取消请假', icon: 'success' })
      } catch (e) {
        uni.showToast({
          title: e instanceof Error ? e.message : '取消失败',
          icon: 'none',
          duration: 3200,
        })
      } finally {
        hideLeaveMutationLoading()
        leaveActionBusy.value = false
      }
    },
  })
}

onShow(() => {
  scrollStyle.value = getPageScrollStyle()
  syncLeaveFromServer()
})

async function toggleTomorrow() {
  if (memberCardBlocked.value && !isTomorrowLeave.value) {
    uni.showToast({ title: '请先购买自律卡包', icon: 'none' })
    return
  }
  if (leaveActionBusy.value) return
  if (leavePrepLocked.value) {
    toastLeavePrepLocked()
    return
  }
  const wasTomorrow = isTomorrowLeave.value
  leaveActionBusy.value = true
  showLeaveMutationLoading(wasTomorrow ? '取消中…' : '提交中…')
  try {
    if (wasTomorrow) {
      await request('/api/user/leave', {
        method: 'POST',
        data: leavePostBody({ type: 'clear_tomorrow' }),
        timeout: LEAVE_POST_TIMEOUT_MS,
      })
      await syncLeaveFromServer({ noBanner: true })
      markMinePageNeedsRefresh()
      uni.showToast({ title: '已取消明天请假', icon: 'success' })
    } else {
      await request('/api/user/leave', {
        method: 'POST',
        data: leavePostBody({ type: 'tomorrow' }),
        timeout: LEAVE_POST_TIMEOUT_MS,
      })
      await syncLeaveFromServer({ noBanner: true })
      markMinePageNeedsRefresh()
      uni.showToast({ title: '已提交明天请假', icon: 'success' })
    }
  } catch (e) {
    uni.showToast({
      title: e instanceof Error ? e.message : wasTomorrow ? '取消失败' : '提交失败',
      icon: 'none',
      duration: 3200,
    })
  } finally {
    hideLeaveMutationLoading()
    leaveActionBusy.value = false
  }
}

async function submitRange() {
  if (memberCardBlocked.value) {
    uni.showToast({ title: '请先购买自律卡包', icon: 'none' })
    return
  }
  if (leaveActionBusy.value) return
  if (leavePrepLocked.value) {
    toastLeavePrepLocked()
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
  showLeaveMutationLoading('提交中…')
  try {
    await request('/api/user/leave', {
      method: 'POST',
      data: leavePostBody({
        type: 'range',
        start: rangeStart.value,
        end: rangeEnd.value,
      }),
      timeout: LEAVE_POST_TIMEOUT_MS,
    })
    await syncLeaveFromServer({ noBanner: true })
    markMinePageNeedsRefresh()
    uni.showToast({ title: '请假成功', icon: 'success' })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/mine/index' })
    }, 1000)
  } catch (e) {
    uni.showToast({
      title: e instanceof Error ? e.message : '提交失败',
      icon: 'none',
      duration: 3200,
    })
  } finally {
    hideLeaveMutationLoading()
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

.leave-period-tabs {
  display: flex;
  flex-direction: row;
  gap: 16rpx;
  margin-bottom: 28rpx;
}

.leave-period-tab {
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

.leave-period-tab--active {
  color: #fff;
  background: #73b054;
  border-color: #73b054;
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
  background: linear-gradient(165deg, #F8FBF6 0%, #fff 55%);
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

.leave-prep-lock-hint {
  margin-top: 8rpx;
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
  display: flex;
  flex-direction: column;
  max-height: 70vh;
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

.range-pick-placeholder {
  width: 100%;
  height: 440rpx;
  min-height: 440rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
}

.range-pick-placeholder__txt {
  font-size: 28rpx;
  font-weight: 700;
  color: $ok-slate-400;
}

.range-pick-view {
  width: 100%;
  height: 440rpx;
  min-height: 440rpx;
  flex-shrink: 0;
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
