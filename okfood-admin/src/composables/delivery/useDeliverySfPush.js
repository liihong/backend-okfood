/** 配送大表 · 顺丰推单（预约 bulk / 及时单）共用逻辑 */

export const SF_PUSH_MODE_SHEET = 'sheet'
export const SF_PUSH_MODE_INSTANT = 'instant'

/** @param {'sheet'|'instant'} mode */
export function getSfPushApiPath(mode) {
  return mode === SF_PUSH_MODE_INSTANT
    ? '/api/admin/delivery-sf/push-instant'
    : '/api/admin/delivery-sf/push'
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
