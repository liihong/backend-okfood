/** 后台单次点餐列表：金额列展示（会员卡支付为 0 元实收） */

export const MEMBER_CARD_PAY_CHANNEL = '会员卡'

/** @param {Record<string, unknown> | null | undefined} row */
export function isMemberCardPaidSingleMeal(row) {
  if (!row || typeof row !== 'object') return false
  return String(row.pay_channel || '').trim() === MEMBER_CARD_PAY_CHANNEL
}

/** @param {Record<string, unknown> | null | undefined} row */
export function singleMealOrderAmountDisplay(row) {
  if (isMemberCardPaidSingleMeal(row)) return '会员卡支付'
  const amt = row?.amount_yuan
  return amt != null && amt !== '' ? String(amt) : '—'
}
