/** 顺丰推单后自助修改生效口径（与份数管理、后端 delivery_sheet_pushed_today 一致） */

/**
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 * @returns {boolean}
 */
export function isDeliverySheetPushedToday(profile) {
  return profile?.delivery_sheet_pushed_today === true
}

/**
 * 编辑页顶部说明（地址、份数等自助修改共用）
 * @param {object | null | undefined} profile
 * @returns {string}
 */
export function sfPushEffectiveEditNotice(profile) {
  if (isDeliverySheetPushedToday(profile)) {
    return '今日配送大表已同步顺丰，修改将自下一配送日起生效；今日配送仍按原信息。'
  }
  return '今日尚未向顺丰推单，保存后立即生效。'
}

/**
 * 保存成功弹窗文案（Toast 字数有限易截断，请配合 showOkAlert）
 * @param {object | null | undefined} profile
 * @param {{ titleScheduled?: string, titleImmediate?: string, contentScheduled?: string, contentImmediate?: string }} [labels]
 * @returns {{ title: string, content: string }}
 */
export function sfPushEffectiveSaveAlert(profile, labels = {}) {
  const {
    titleScheduled = '已保存',
    titleImmediate = '已保存',
    contentScheduled = '今日配送大表已同步顺丰，本次修改自下一配送日起生效；今日配送仍按原信息。',
    contentImmediate = '今日尚未向顺丰推单，本次修改保存后立即生效。',
  } = labels
  if (isDeliverySheetPushedToday(profile)) {
    return { title: titleScheduled, content: contentScheduled }
  }
  return { title: titleImmediate, content: contentImmediate }
}
