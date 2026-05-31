import { ref } from 'vue'

/** @typedef {import('./memberCouponScope.js').MemberCouponItem} MemberCouponItem */

/**
 * @typedef {object} CouponReminderPayload
 * @property {number} count
 * @property {string} maxDiscountYuan
 * @property {MemberCouponItem[]} coupons
 */

export const couponReminderVisible = ref(false)

/** @type {import('vue').Ref<CouponReminderPayload|null>} */
export const couponReminderPayload = ref(null)

/** @param {CouponReminderPayload} payload */
export function showCouponReminderModal(payload) {
  couponReminderPayload.value = payload
  couponReminderVisible.value = true
}

export function hideCouponReminderModal() {
  couponReminderVisible.value = false
}
