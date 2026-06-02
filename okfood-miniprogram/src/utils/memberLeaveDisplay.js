import { ymdTodayShanghai } from './memberDeliveryDate'

/** API 日期字段转 YYYY-MM-DD */
export function ymdFromApi(d) {
  if (d == null || d === '') return ''
  const s = String(d)
  return s.length >= 10 ? s.slice(0, 10) : s
}

/** 展示用：如「5月28日」 */
export function ymdToCnMd(ymd) {
  const raw = ymdFromApi(ymd)
  if (!raw) return ''
  const parts = raw.split('-')
  if (parts.length < 3) return ''
  const m = Number(parts[1])
  const d = Number(parts[2])
  if (!m || !d) return ''
  return `${m}月${d}日`
}

/** 从 leave_range 提取起止 YMD */
export function leaveRangeYmdPair(leaveRange) {
  if (!leaveRange || typeof leaveRange !== 'object') {
    return { start: '', end: '' }
  }
  return {
    start: leaveRange.start != null ? String(leaveRange.start).slice(0, 10) : '',
    end: leaveRange.end != null ? String(leaveRange.end).slice(0, 10) : '',
  }
}

/** 上海业务日是否落在区间请假内（闭区间） */
export function isOnLeaveTodayShanghai(leaveRange, todayYmd = ymdTodayShanghai()) {
  const { start, end } = leaveRangeYmdPair(leaveRange)
  if (!start || !end) return false
  return todayYmd >= start && todayYmd <= end
}

/** 是否已配置区间请假（含尚未开始的未来区间） */
export function hasLeaveRangeConfigured(leaveRange) {
  const { start, end } = leaveRangeYmdPair(leaveRange)
  return Boolean(start && end)
}

/** 区间请假仍生效或尚未开始（结束日 >= 上海业务日） */
export function isLeaveRangeActiveOrFuture(leaveRange, todayYmd = ymdTodayShanghai()) {
  const { start, end } = leaveRangeYmdPair(leaveRange)
  if (!start || !end) return false
  return end >= todayYmd
}

/** 「仅明天请假」是否仍有效（目标业务日未过） */
export function isTomorrowLeaveActive(isLeavedTomorrow, targetYmd, todayYmd = ymdTodayShanghai()) {
  if (!isLeavedTomorrow) return false
  const t = ymdFromApi(targetYmd)
  if (!t) return true
  return t >= todayYmd
}

/** 区间请假在计划卡上的展示文案 */
function formatRangeLeaveLine(leaveRange) {
  const { start: sRaw, end: eRaw } = leaveRangeYmdPair(leaveRange)
  const sm = ymdToCnMd(sRaw)
  const em = ymdToCnMd(eRaw)
  if (!sm || !em) return ''
  if (sRaw === eRaw) return `${sm}请假中`
  return `${sm}到${em}请假中`
}

/**
 * 计划卡右上角：每日份数 / 请假 / 暂停配送
 * @param {{
 *   isLoggedIn?: boolean
 *   hideDailyUnits?: boolean
 *   isPaused?: boolean
 *   dailyUnits?: number
 *   leaveRange?: object | null
 *   isLeavedTomorrow?: boolean
 *   tomorrowLeaveTargetYmd?: string
 * }} [options]
 */
export function formatPlanCardDailyUnitsLine(options = {}) {
  const {
    isLoggedIn = false,
    hideDailyUnits = false,
    isPaused = false,
    dailyUnits = 1,
    leaveRange = null,
    isLeavedTomorrow = false,
    tomorrowLeaveTargetYmd = '',
  } = options

  if (!isLoggedIn || hideDailyUnits) return ''
  if (isPaused) return '已暂停配送'

  if (isOnLeaveTodayShanghai(leaveRange)) {
    return formatRangeLeaveLine(leaveRange) || '请假中'
  }

  if (isLeaveRangeActiveOrFuture(leaveRange) && !isOnLeaveTodayShanghai(leaveRange)) {
    return formatRangeLeaveLine(leaveRange) || '已预约请假'
  }

  if (isTomorrowLeaveActive(isLeavedTomorrow, tomorrowLeaveTargetYmd)) return '明日请假中'

  const n = Math.max(1, Math.floor(Number(dailyUnits) || 0))
  return `每日 ${n} 份`
}
