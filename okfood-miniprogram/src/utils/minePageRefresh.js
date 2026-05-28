/** 子页修改会员/会员卡相关数据后标记，「我的」页 onShow 消费并拉取最新档案 */
export const MINE_NEEDS_REFRESH_KEY = 'okfood_mine_needs_refresh'

/** 会员档案、地址、份数、请假等变更成功后调用 */
export function markMinePageNeedsRefresh() {
  try {
    uni.setStorageSync(MINE_NEEDS_REFRESH_KEY, '1')
  } catch {
    /* ignore */
  }
}

/** @returns {boolean} 是否曾标记需刷新（读后清除） */
export function consumeMinePageNeedsRefresh() {
  try {
    const v = uni.getStorageSync(MINE_NEEDS_REFRESH_KEY)
    if (v === '1' || v === 1 || v === true) {
      uni.removeStorageSync(MINE_NEEDS_REFRESH_KEY)
      return true
    }
  } catch {
    /* ignore */
  }
  return false
}
