/**
 * 厨师备货看板：哪些零售分类要展示、用什么计量单位。
 * 与后台「零售分类」名称精确匹配。
 */

/** 不进备货看板的分类 */
export const PREP_BOARD_EXCLUDED_CATEGORY_NAMES = ['果蔬汁', '月饼']

/** 分类名 → 备货单位（未配置则默认「盒」） */
export const PREP_BOARD_QTY_UNIT_BY_CATEGORY = {
  代餐粉: '套',
}

/**
 * @param {unknown} name
 */
export function isPrepBoardCategoryName(name) {
  const n = String(name || '').trim()
  if (!n) return true
  return !PREP_BOARD_EXCLUDED_CATEGORY_NAMES.includes(n)
}

/**
 * @param {unknown} categoryName
 */
export function prepBoardQtyUnit(categoryName) {
  const n = String(categoryName || '').trim()
  if (n && PREP_BOARD_QTY_UNIT_BY_CATEGORY[n]) return PREP_BOARD_QTY_UNIT_BY_CATEGORY[n]
  return '盒'
}