/**
 * 购卡结算：客户端按模板筛选可用券（与后端 scope 规则对齐，用于 available 接口不可用时的兜底）
 */

/**
 * @typedef {object} MemberCouponItem
 * @property {number} id
 * @property {string|null} [template_name]
 * @property {string} [discount_yuan]
 * @property {string} [min_order_yuan]
 * @property {string} [biz_type]
 * @property {string} [scope_level]
 * @property {number|null} [scope_target_id]
 * @property {string|null} [usage_instructions]
 * @property {string|null} [expires_at]
 */

/**
 * @param {MemberCouponItem[]|null|undefined} coupons
 * @param {number|string} templateId
 * @returns {MemberCouponItem[]}
 */
export function filterMemberCardCouponsForTemplate(coupons, templateId) {
  const tid = Math.floor(Number(templateId))
  if (!tid) return []
  const list = Array.isArray(coupons) ? coupons : []
  return list.filter((c) => {
    const biz = String(c?.biz_type || '').trim()
    if (biz !== 'member_card' && biz !== 'all') return false
    const level = String(c?.scope_level || 'all').trim()
    if (level === 'all' || biz === 'all') return true
    if (level === 'membership_template') {
      const target = c?.scope_target_id != null ? Math.floor(Number(c.scope_target_id)) : 0
      return target === tid
    }
    // 周卡/月卡范围：模板购卡单在服务端会带 card_kind，客户端无法从模板 id 推断，先展示由支付时再校验
    if (level === 'week_month') return true
    return false
  })
}

/**
 * @param {MemberCouponItem[]|null|undefined} coupons
 * @returns {MemberCouponItem|null}
 */
export function pickBestMemberCoupon(coupons) {
  const list = Array.isArray(coupons) ? coupons : []
  if (!list.length) return null
  return list.reduce((best, cur) => {
    const bd = Number(best?.discount_yuan)
    const cd = Number(cur?.discount_yuan)
    const b = Number.isFinite(bd) ? bd : 0
    const c = Number.isFinite(cd) ? cd : 0
    return c > b ? cur : best
  }, list[0])
}
