/** 份数展示与保存结果文案（与后端 daily_meal_units / pending / 推单冻结口径一致） */

/**
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 * @returns {number}
 */
export function effectiveDailyMealUnitsFromProfile(profile) {
  const n = Math.floor(Number(profile?.daily_meal_units) || 0)
  return n >= 1 && n <= 50 ? n : 1
}

/**
 * @param {object | null | undefined} profile
 * @returns {number | null}
 */
export function pendingDailyMealUnitsFromProfile(profile) {
  const raw = profile?.daily_meal_units_pending
  if (raw == null) return null
  const n = Math.floor(Number(raw))
  if (!Number.isFinite(n) || n < 1 || n > 50) return null
  return n
}

/**
 * 计划卡/地址区附带的份数说明行
 * @param {object | null | undefined} profile
 * @returns {string}
 */
export function formatDailyMealUnitsHintLine(profile) {
  const current = effectiveDailyMealUnitsFromProfile(profile)
  const pending = pendingDailyMealUnitsFromProfile(profile)
  if (pending != null && pending !== current) {
    return `每日配送 ${current} 份（已预约改为 ${pending} 份）`
  }
  return `每日配送 ${current} 份`
}

/**
 * 份数管理页：步进器初始值（有 pending 时展示目标值）
 * @param {object | null | undefined} profile
 * @returns {number}
 */
export function dailyMealUnitsEditorValueFromProfile(profile) {
  const pending = pendingDailyMealUnitsFromProfile(profile)
  if (pending != null) return pending
  return effectiveDailyMealUnitsFromProfile(profile)
}

/**
 * @param {object | null | undefined} profile PATCH /api/user/profile 返回的 data
 * @returns {string}
 */
export function dailyMealUnitsSaveToastFromProfile(profile) {
  const pending = pendingDailyMealUnitsFromProfile(profile)
  const current = effectiveDailyMealUnitsFromProfile(profile)
  if (pending != null && pending !== current) {
    return `已预约：今日仍 ${current} 份，下一配送日起 ${pending} 份`
  }
  return '已保存，立即生效'
}

/**
 * 顺丰履约锁：禁止自助改份数
 * @param {object | null | undefined} profile
 * @returns {boolean} true=可继续
 */
export function guardSfSelfServiceLocked(profile) {
  if (profile?.sf_self_service_locked !== true) return true
  uni.showModal({
    title: '暂时无法修改',
    content: '您的订单已同步顺丰配送，送达完成后可修改份数。',
    showCancel: false,
    confirmText: '知道了',
    confirmColor: '#73B054',
  })
  return false
}
