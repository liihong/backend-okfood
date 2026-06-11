/** 果蔬汁/商城下单开关：后厨就绪后改为 true 即可放开 */
export const RETAIL_ORDER_ENABLED = false

/** 零售下单未开放时的提示 */
export function showRetailComingSoon() {
  uni.showToast({ title: '待上线', icon: 'none' })
}
