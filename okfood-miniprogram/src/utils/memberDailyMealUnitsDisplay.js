/** 份数展示与保存结果文案（与后端 daily_meal_units / pending / 推单冻结口径一致） */

import { sfPushEffectiveSaveAlert } from '@/utils/memberSfPushEffectiveHint.js'
import {
  MEAL_PERIOD_LUNCH,
  MEAL_PERIOD_DINNER,
  dailyMealUnitsFieldsForPeriod,
  entitledMealPeriodsFromProfile,
  mealPeriodLabel,
} from '@/utils/memberMealPeriod.js'

/**
 * @param {object | null | undefined} profile
 * @param {'lunch'|'dinner'} [period]
 */
function unitsSlice(profile, period = MEAL_PERIOD_LUNCH) {
  if (!profile || typeof profile !== 'object') return {}
  if (period === MEAL_PERIOD_LUNCH) {
    return {
      daily_meal_units: profile.daily_meal_units,
      daily_meal_units_pending: profile.daily_meal_units_pending,
      delivery_sheet_pushed_today: profile.delivery_sheet_pushed_today,
      sf_self_service_locked: profile.sf_self_service_locked,
    }
  }
  return dailyMealUnitsFieldsForPeriod(profile, period)
}

/**
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 * @param {'lunch'|'dinner'} [period]
 * @returns {number}
 */
export function effectiveDailyMealUnitsFromProfile(profile, period = MEAL_PERIOD_LUNCH) {
  const slice = unitsSlice(profile, period)
  const n = Math.floor(Number(slice.daily_meal_units) || 0)
  return n >= 1 && n <= 50 ? n : 1
}

/**
 * @param {object | null | undefined} profile
 * @param {'lunch'|'dinner'} [period]
 * @returns {number | null}
 */
export function pendingDailyMealUnitsFromProfile(profile, period = MEAL_PERIOD_LUNCH) {
  const raw = unitsSlice(profile, period).daily_meal_units_pending
  if (raw == null) return null
  const n = Math.floor(Number(raw))
  if (!Number.isFinite(n) || n < 1 || n > 50) return null
  return n
}

/**
 * 单个已开通餐段的份数短句，如「晚餐 1 份/日」
 * @param {object | null | undefined} profile
 * @param {'lunch'|'dinner'} period
 * @returns {string}
 */
function periodUnitsPhrase(profile, period) {
  const cur = effectiveDailyMealUnitsFromProfile(profile, period)
  const pending = pendingDailyMealUnitsFromProfile(profile, period)
  let line = `${mealPeriodLabel(period)} ${cur} 份/日`
  if (pending != null && pending !== cur) {
    line += `（已预约 ${pending} 份）`
  }
  return line
}

/**
 * 计划卡/地址区附带的份数说明行。
 * 只展示 entitled_meal_periods 里已开通的餐段：纯晚餐卡不带午餐。
 * 会员表 daily_meal_units 默认是 1，不能据此判断有午餐。
 * @param {object | null | undefined} profile
 * @returns {string}
 */
export function formatDailyMealUnitsHintLine(profile) {
  const periods = entitledMealPeriodsFromProfile(profile)
  const hasLunch = periods.includes(MEAL_PERIOD_LUNCH)
  const hasDinner = periods.includes(MEAL_PERIOD_DINNER)
  // 仅午餐：保持原「每日配送」文案
  if (hasLunch && !hasDinner) {
    const lunchCur = effectiveDailyMealUnitsFromProfile(profile, MEAL_PERIOD_LUNCH)
    const lunchPending = pendingDailyMealUnitsFromProfile(profile, MEAL_PERIOD_LUNCH)
    if (lunchPending != null && lunchPending !== lunchCur) {
      return `每日配送 ${lunchCur} 份（已预约改为 ${lunchPending} 份）`
    }
    return `每日配送 ${lunchCur} 份`
  }
  const parts = []
  if (hasLunch) parts.push(periodUnitsPhrase(profile, MEAL_PERIOD_LUNCH))
  if (hasDinner) parts.push(periodUnitsPhrase(profile, MEAL_PERIOD_DINNER))
  return parts.join(' · ')
}

/**
 * @param {object | null | undefined} profile
 * @param {'lunch'|'dinner'} [period]
 */
export function dailyMealUnitsEditorValueFromProfile(profile, period = MEAL_PERIOD_LUNCH) {
  const pending = pendingDailyMealUnitsFromProfile(profile, period)
  if (pending != null) return pending
  return effectiveDailyMealUnitsFromProfile(profile, period)
}

/**
 * @param {object | null | undefined} profile
 * @param {'lunch'|'dinner'} [period]
 */
export function dailyMealUnitsSaveAlertFromProfile(profile, period = MEAL_PERIOD_LUNCH) {
  const pending = pendingDailyMealUnitsFromProfile(profile, period)
  const current = effectiveDailyMealUnitsFromProfile(profile, period)
  const label = mealPeriodLabel(period)
  if (pending != null && pending !== current) {
    return {
      title: '已预约',
      content: `${label}今日仍为 ${current} 份；自下一配送日起改为 ${pending} 份。`,
    }
  }
  const slice = unitsSlice(profile, period)
  return sfPushEffectiveSaveAlert(
    {
      delivery_sheet_pushed_today: slice.delivery_sheet_pushed_today,
    },
    {
      contentScheduled: `${label}配送大表已同步顺丰，份数修改自下一配送日起生效；今日仍为原份数。`,
      contentImmediate: `今日${label}尚未向顺丰推单，份数修改保存后立即生效。`,
    },
  )
}

/**
 * @param {object | null | undefined} profile
 * @param {'lunch'|'dinner'} [period]
 */
export function dailyMealUnitsSaveToastFromProfile(profile, period = MEAL_PERIOD_LUNCH) {
  const pending = pendingDailyMealUnitsFromProfile(profile, period)
  const current = effectiveDailyMealUnitsFromProfile(profile, period)
  if (pending != null && pending !== current) {
    return `已预约：今日仍 ${current} 份，下一配送日起 ${pending} 份`
  }
  return '已保存，立即生效'
}

/**
 * @param {object | null | undefined} profile
 * @param {'lunch'|'dinner'} [period]
 */
export function guardSfSelfServiceLocked(profile, period = MEAL_PERIOD_LUNCH) {
  const locked = unitsSlice(profile, period).sf_self_service_locked === true
  if (!locked) return true
  const label = mealPeriodLabel(period)
  uni.showModal({
    title: '暂时无法修改',
    content: `您的${label}订单已同步顺丰配送，送达完成后可修改份数。`,
    showCancel: false,
    confirmText: '知道了',
    confirmColor: '#73B054',
  })
  return false
}
