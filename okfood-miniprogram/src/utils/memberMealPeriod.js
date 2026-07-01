/** 午/晚餐餐段：从 GET /api/user/me 解析 entitled_meal_periods 与各餐段字段 */

import {
  isLeaveRangeActiveOrFuture,
  isOnLeaveTodayShanghai,
  isTomorrowLeaveActive,
  ymdFromApi,
  ymdToCnMd,
} from '@/utils/memberLeaveDisplay.js'
import { ymdTodayShanghai } from '@/utils/memberDeliveryDate.js'

export const MEAL_PERIOD_LUNCH = 'lunch'
export const MEAL_PERIOD_DINNER = 'dinner'
/** 全天请假：后端同时写入已开通的午/晚餐请假字段 */
export const MEAL_PERIOD_ALL = 'all'

/** @param {object | null | undefined} profile */
export function entitledMealPeriodsFromProfile(profile) {
  const raw = profile?.entitled_meal_periods
  if (!Array.isArray(raw) || !raw.length) return [MEAL_PERIOD_LUNCH]
  const out = []
  for (const x of raw) {
    const s = String(x || '').trim().toLowerCase()
    if ((s === MEAL_PERIOD_LUNCH || s === MEAL_PERIOD_DINNER) && !out.includes(s)) out.push(s)
  }
  return out.length ? out : [MEAL_PERIOD_LUNCH]
}

/** @param {object | null | undefined} profile */
export function hasDinnerEntitlement(profile) {
  return entitledMealPeriodsFromProfile(profile).includes(MEAL_PERIOD_DINNER)
}

/** 请假页可选餐段：午餐 / 晚餐 / 全天（双餐段才有全天） */
export function leaveMealPeriodTabOptions(profile) {
  const entitled = entitledMealPeriodsFromProfile(profile)
  const tabs = []
  if (entitled.includes(MEAL_PERIOD_LUNCH)) tabs.push(MEAL_PERIOD_LUNCH)
  if (entitled.includes(MEAL_PERIOD_DINNER)) tabs.push(MEAL_PERIOD_DINNER)
  if (entitled.includes(MEAL_PERIOD_LUNCH) && entitled.includes(MEAL_PERIOD_DINNER)) {
    tabs.push(MEAL_PERIOD_ALL)
  }
  return tabs.length ? tabs : [MEAL_PERIOD_LUNCH]
}

/** @param {object | null | undefined} profile @param {'lunch'|'dinner'} period */
export function balanceForPeriod(profile, period) {
  if (!profile || typeof profile !== 'object') return 0
  if (period === MEAL_PERIOD_DINNER) {
    return Math.max(0, Math.floor(Number(profile.dinner_balance) || 0))
  }
  return Math.max(0, Math.floor(Number(profile.balance) || 0))
}

/** 午餐或晚餐任一有余次即视为仍有餐次 */
export function hasAnyMealBalance(profile) {
  if (!profile || typeof profile !== 'object') return false
  if (balanceForPeriod(profile, MEAL_PERIOD_LUNCH) > 0) return true
  if (hasDinnerEntitlement(profile) && balanceForPeriod(profile, MEAL_PERIOD_DINNER) > 0) {
    return true
  }
  return false
}

/** @param {object | null | undefined} profile @param {'lunch'|'dinner'} period */
export function leaveFieldsForPeriod(profile, period) {
  if (period === MEAL_PERIOD_DINNER) {
    return {
      is_leaved_tomorrow: profile?.dinner_is_leaved_tomorrow === true,
      tomorrow_leave_target_date: profile?.dinner_tomorrow_leave_target_date ?? null,
      leave_range: profile?.dinner_leave_range ?? null,
      sf_self_service_locked: profile?.dinner_sf_self_service_locked === true,
    }
  }
  return {
    is_leaved_tomorrow: profile?.is_leaved_tomorrow === true,
    tomorrow_leave_target_date: profile?.tomorrow_leave_target_date ?? null,
    leave_range: profile?.leave_range ?? null,
    sf_self_service_locked: profile?.sf_self_service_locked === true,
  }
}

/** @param {object | null | undefined} profile @param {'lunch'|'dinner'} period */
export function dailyMealUnitsFieldsForPeriod(profile, period) {
  if (period === MEAL_PERIOD_DINNER) {
    return {
      daily_meal_units: profile?.dinner_daily_meal_units,
      daily_meal_units_pending: profile?.dinner_daily_meal_units_pending,
      delivery_sheet_pushed_today: profile?.dinner_delivery_sheet_pushed_today === true,
      sf_self_service_locked: profile?.dinner_sf_self_service_locked === true,
    }
  }
  return {
    daily_meal_units: profile?.daily_meal_units,
    daily_meal_units_pending: profile?.daily_meal_units_pending,
    delivery_sheet_pushed_today: profile?.delivery_sheet_pushed_today === true,
    sf_self_service_locked: profile?.sf_self_service_locked === true,
  }
}

/** @param {'lunch'|'dinner'|'all'} period */
export function mealPeriodLabel(period) {
  if (period === MEAL_PERIOD_DINNER) return '晚餐'
  if (period === MEAL_PERIOD_ALL) return '全天'
  return '午餐'
}

/**
 * 单餐段请假状态短文案（供「我的」页展示）
 * @param {object | null | undefined} profile
 * @param {'lunch'|'dinner'} period
 * @param {string} [todayYmd]
 * @returns {string}
 */
export function leaveStatusBriefForPeriod(profile, period, todayYmd = ymdTodayShanghai()) {
  const f = leaveFieldsForPeriod(profile, period)
  const lr = f.leave_range
  if (isOnLeaveTodayShanghai(lr, todayYmd)) return '请假中'
  if (isTomorrowLeaveActive(f.is_leaved_tomorrow, ymdFromApi(f.tomorrow_leave_target_date))) {
    return '明日请假'
  }
  if (isLeaveRangeActiveOrFuture(lr, todayYmd) && !isOnLeaveTodayShanghai(lr, todayYmd)) {
    const s = lr?.start != null ? String(lr.start).slice(0, 10) : ''
    const e = lr?.end != null ? String(lr.end).slice(0, 10) : ''
    const sm = ymdToCnMd(s)
    const em = ymdToCnMd(e)
    if (sm && em) return s === e ? `${sm}起请假` : `${sm}-${em}请假`
    return '已预约请假'
  }
  return ''
}

/**
 * 合并午/晚餐请假状态（双餐段会员）
 * @param {object | null | undefined} profile
 */
export function combinedLeaveStatusLine(profile) {
  if (!profile || typeof profile !== 'object') return ''
  const today = ymdTodayShanghai()
  const lunch = leaveStatusBriefForPeriod(profile, MEAL_PERIOD_LUNCH, today)
  if (!hasDinnerEntitlement(profile)) return lunch
  const dinner = leaveStatusBriefForPeriod(profile, MEAL_PERIOD_DINNER, today)
  const parts = []
  if (lunch) parts.push(`午餐${lunch}`)
  if (dinner) parts.push(`晚餐${dinner}`)
  return parts.join(' · ')
}
