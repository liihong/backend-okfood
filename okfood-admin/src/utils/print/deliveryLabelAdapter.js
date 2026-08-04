/** 餐别文案：优先使用会员开卡种类名称 */

/**
 * 配送大表备餐短号：{片区编码}{3位序号}，如 ZX001。
 * 未配置片区编码时用 X 占位。
 * @param {string} regionName
 * @param {number|null|undefined} stopIndex 片区内停靠点序号（从 1 起）
 * @param {Record<string, string>|null|undefined} regionCodeByName
 */
export function formatDeliveryPrepOrderNo(regionName, stopIndex, regionCodeByName) {
  const name = String(regionName || '').trim()
  const map = regionCodeByName && typeof regionCodeByName === 'object' ? regionCodeByName : {}
  let code = String(map[name] || '').trim().toUpperCase()
  if (!code) code = 'X'
  const seq = Math.max(1, Math.floor(Number(stopIndex) || 1))
  return `${code}${String(seq).padStart(3, '0')}`
}

/**
 * @param {{ card_kind_label?: string | null }} member
 */
export function buildMealCategory(member) {
  const label = String(member?.card_kind_label || '').trim()
  if (label) return label
  return '午餐卡'
}

/** 餐别短文案：午晚餐卡 → 午+晚 */
export function formatMealCategoryShort(label) {
  let s = String(label || '').trim().replace(/卡/g, '').replace(/\s/g, '')
  if (!s) return '午'
  s = s.replace(/午餐/g, '午').replace(/晚餐/g, '晚')
  if (s === '午晚' || s === '午晚餐' || (s.includes('午晚') && !s.includes('+'))) return '午+晚'
  return s
}

/**
 * @param {object[]} flatStops
 * @param {string} deliveryDate
 * @param {string|null} filterRegion
 * @param {function} addressLineForExport
 * @param {string} storeName
 * @param {Record<string, string>} [regionCodeByName]
 */
export function buildDeliveryLabelItems(
  flatStops,
  deliveryDate,
  filterRegion,
  addressLineForExport,
  storeName,
  regionCodeByName = {},
) {
  const out = []
  const store = String(storeName || 'OK饭').trim() || 'OK饭'
  for (const st of flatStops || []) {
    if (st.groupArea === '门店自提') continue
    if (filterRegion && st.groupArea !== filterRegion) continue
    const region = st.groupArea ?? st.area ?? ''
    const prepOrderNo = formatDeliveryPrepOrderNo(region, st.stopIndex, regionCodeByName)
    for (const m of st.members || []) {
      const phone = m.phone != null ? String(m.phone) : ''
      const remark = m.remarks != null ? String(m.remarks) : ''
      out.push({
        region,
        store_name: store,
        address: addressLineForExport(st),
        name: m.name != null ? String(m.name) : '',
        phone_tail: phone.length >= 4 ? phone.slice(-4) : phone,
        phone_masked: maskPhone(phone),
        plan_type: m.plan_type != null ? String(m.plan_type) : '',
        meal_category: buildMealCategory(m),
        units: Number(m.daily_meal_units) || 1,
        remark,
        delivery_date: deliveryDate,
        route_seq: st.stopIndex ?? null,
        shop_order_id: st.shop_order_id != null ? String(st.shop_order_id) : '',
        sf_order_id: st.sf_order_id != null ? String(st.sf_order_id) : '',
        product_title: '',
        order_no: prepOrderNo,
        store_pickup: st.groupArea === '门店自提' || m.store_pickup === true,
        order_kind: 'delivery',
      })
    }
  }
  return out
}

/** 返回未配置编码的片区名（去重） */
export function missingRegionCodesForStops(flatStops, regionCodeByName = {}) {
  const map = regionCodeByName && typeof regionCodeByName === 'object' ? regionCodeByName : {}
  const missing = new Set()
  for (const st of flatStops || []) {
    if (st.groupArea === '门店自提') continue
    const name = String(st.groupArea ?? st.area ?? '').trim()
    if (!name) continue
    if (!String(map[name] || '').trim()) missing.add(name)
  }
  return [...missing]
}

function maskPhone(phone) {
  const p = String(phone || '').trim()
  if (p.length >= 11) return `${p.slice(0, 3)}****${p.slice(-4)}`
  if (p.length >= 7) return `${p.slice(0, 3)}****${p.slice(-4)}`
  return p
}
