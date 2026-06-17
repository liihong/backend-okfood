/** 配送大表 · 顺丰推单（预约 bulk / 及时单）共用逻辑 */

export const SF_PUSH_MODE_SHEET = 'sheet'
export const SF_PUSH_MODE_INSTANT = 'instant'

/** 大表视图：午餐 / 晚餐 / 午晚餐双餐段运维 */
export const SHEET_VIEW_LUNCH = 'lunch'
export const SHEET_VIEW_DINNER = 'dinner'
export const SHEET_VIEW_LUNCH_DINNER = 'lunch_dinner'

/** @param {'lunch'|'dinner'|'lunch_dinner'} sheetView */
export function getDeliverySheetApiPath(sheetView) {
  if (sheetView === SHEET_VIEW_DINNER) return '/api/admin/delivery-sheet/dinner'
  if (sheetView === SHEET_VIEW_LUNCH_DINNER) return '/api/admin/delivery-sheet/lunch-dinner'
  return '/api/admin/delivery-sheet'
}

/** @param {'lunch'|'dinner'|'lunch_dinner'} sheetView @param {'sheet'|'instant'} mode */
export function getSfPushPreviewApiPath(sheetView, mode) {
  if (sheetView === SHEET_VIEW_DINNER) return '/api/admin/delivery-sf/dinner/preview'
  return mode === SF_PUSH_MODE_INSTANT
    ? '/api/admin/delivery-sf/preview'
    : '/api/admin/delivery-sf/preview'
}

/** @param {'lunch'|'dinner'|'lunch_dinner'} sheetView @param {'sheet'|'instant'} mode */
export function getSfPushApiPath(mode, sheetView = SHEET_VIEW_LUNCH) {
  if (sheetView === SHEET_VIEW_DINNER) return '/api/admin/delivery-sf/dinner/push'
  return mode === SF_PUSH_MODE_INSTANT
    ? '/api/admin/delivery-sf/push-instant'
    : '/api/admin/delivery-sf/push'
}

/** 午晚餐运维视图仅展示名单，推顺丰仍走午餐/晚餐独立入口 */
export function sheetViewSupportsSfPush(sheetView) {
  return sheetView === SHEET_VIEW_LUNCH || sheetView === SHEET_VIEW_DINNER
}

/** 人工标记送达时传给后端的 meal_period */
export function deliveryMarkMealPeriod(sheetView) {
  return sheetView === SHEET_VIEW_DINNER ? 'dinner' : 'lunch'
}

/**
 * 预览数据是否满足当前模式的推单前置条件
 * @param {{ sf_configured?: boolean, instant_sf_configured?: boolean } | null | undefined} preview
 * @param {'sheet'|'instant'} mode
 */
export function isSfPushConfigured(preview, mode) {
  if (mode === SF_PUSH_MODE_INSTANT) {
    return Boolean(preview?.instant_sf_configured)
  }
  return Boolean(preview?.sf_configured)
}

/**
 * 预约推单：校验期望送达须晚于当前时刻（立即推单行跳过）
 * @returns {string | null} 错误文案；null 表示通过
 */
export function validateSfSheetPushRows(rows, deliveryDate, helpers) {
  const { defaultSfExpectAt, effectiveSfExpectDefaultYmd, parseSfExpectAtShanghai } = helpers
  const d0 = String(deliveryDate || '').trim()
  for (const r of rows || []) {
    if (!r.selected || r.already_pushed || r.push_immediately) continue
    const expectAt = r.expect_delivery_at || defaultSfExpectAt(effectiveSfExpectDefaultYmd(d0))
    const t = parseSfExpectAtShanghai(expectAt)
    if (!t || t.getTime() < Date.now()) {
      return '存在未选「立即推单」的停靠点：期望送达须晚于当前时间。历史业务日请选今日及之后的日期时段。'
    }
  }
  return null
}

/**
 * 组装推单请求体
 * @param {object[]} rows
 * @param {string} deliveryDate
 * @param {'sheet'|'instant'} mode
 */
export function buildSfPushPayload(rows, deliveryDate, mode, helpers) {
  const { defaultSfExpectAt } = helpers
  const d0 = String(deliveryDate || '').trim()
  return {
    delivery_date: d0,
    rows: (rows || []).map((r) => {
      const mapT = String(r.map_location_text ?? r.recv_address ?? '').trim()
      const doorD = String(r.door_detail ?? r.recv_building ?? '').trim()
      let expectAt = r.expect_delivery_at
      if (mode === SF_PUSH_MODE_INSTANT || r.push_immediately) {
        expectAt = null
      } else {
        expectAt = expectAt || defaultSfExpectAt(d0)
      }
      return {
        ...r,
        map_location_text: mapT,
        door_detail: doorD,
        recv_address: mapT,
        recv_building: doorD,
        goods_value_yuan: r.is_insured ? r.goods_value_yuan : null,
        expect_delivery_at: expectAt,
        ...(mode === SF_PUSH_MODE_INSTANT ? { push_immediately: true } : {}),
      }
    }),
  }
}
