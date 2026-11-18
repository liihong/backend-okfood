/**
 * 商城零售 SKU 领域工具：规格可选性、默认规格、购物车行组装。
 * 供菜单页规格抽屉与商品详情页共用，避免重复逻辑。
 */

/** @typedef {object} RetailSkuPublic
 * @property {number} id
 * @property {string} [spec_label]
 * @property {string|number|null} [unit_price_yuan]
 * @property {string|number|null} [list_price_yuan]
 * @property {boolean} [is_on_shelf]
 * @property {boolean} [stock_limited]
 * @property {number|null} [stock_remaining]
 * @property {number|null} [sold_count]
 */

/** @typedef {object} RetailSpuDetailLike
 * @property {number} id
 * @property {string} title
 * @property {string|null} [subtitle]
 * @property {string|null} [cover_image_url]
 * @property {string[]|null} [gallery_urls]
 * @property {string|number|null} [price_min_yuan]
 * @property {RetailSkuPublic[]} [skus]
 */

/**
 * 判断 SKU 是否可在前端选择（上架且有库存）。
 * @param {RetailSkuPublic|null|undefined} sku
 */
export function isRetailSkuSelectable(sku) {
  if (!sku?.is_on_shelf) return false
  if (sku.stock_limited && sku.stock_remaining != null && Number(sku.stock_remaining) <= 0) {
    return false
  }
  return true
}

/**
 * 从列表中选取默认可售规格；若无则可售则回退第一项。
 * @param {RetailSkuPublic[]} skus
 */
export function pickDefaultRetailSku(skus) {
  const list = Array.isArray(skus) ? skus : []
  return list.find(isRetailSkuSelectable) || list[0] || null
}

/**
 * 选中规格后的展示价。
 * @param {RetailSkuPublic|null} sku
 * @param {RetailSpuDetailLike|null} detail
 */
export function formatRetailSkuPriceText(sku, detail) {
  if (sku?.unit_price_yuan != null) return Number(sku.unit_price_yuan).toFixed(2)
  const min = detail?.price_min_yuan
  return min != null ? Number(min).toFixed(2) : '0.00'
}

/** @param {RetailSkuPublic|null} sku */
export function formatRetailSkuListPriceText(sku) {
  const lp = sku?.list_price_yuan
  if (lp == null || String(lp).trim() === '') return ''
  return Number(lp).toFixed(2)
}

/**
 * 计算数量步进上限（库存与单笔上限 50）。
 * @param {number} quantity
 * @param {number} delta
 * @param {RetailSkuPublic|null} sku
 */
export function nextRetailSkuQuantity(quantity, delta, sku) {
  const d = Number(delta) || 0
  let next = Math.max(1, (Number(quantity) || 1) + d)
  if (sku?.stock_limited && sku.stock_remaining != null) {
    next = Math.min(next, Math.max(1, Number(sku.stock_remaining)))
  }
  return Math.min(next, 50)
}

/**
 * 组装写入本地购物车的商品快照。
 * @param {RetailSpuDetailLike} detail
 * @param {RetailSkuPublic} sku
 * @param {string} [coverUrl] 已优化或原始封面图
 * @returns {import('@/utils/retailCart/retailCartTypes.js').RetailCartProductInput|null}
 */
export function buildRetailCartProductFromSpu(detail, sku, coverUrl = '') {
  if (!detail || !sku) return null
  const title = sku.spec_label ? `${detail.title} · ${sku.spec_label}` : detail.title
  const cover =
    coverUrl ||
    (Array.isArray(detail.gallery_urls)
      ? String(detail.gallery_urls.find((u) => String(u || '').trim()) || '')
      : '') ||
    (detail.cover_image_url != null ? String(detail.cover_image_url) : '')
  return {
    retailProductId: Number(sku.id),
    spuId: Number(detail.id),
    spuTitle: detail.title,
    specLabel: sku.spec_label || '',
    title,
    unitPriceYuan: sku.unit_price_yuan,
    listPriceYuan: sku.list_price_yuan,
    coverImageUrl: cover,
    stockRemaining: sku.stock_remaining != null ? Number(sku.stock_remaining) : null,
    stockLimited: !!sku.stock_limited,
    soldCount: sku.sold_count != null ? Number(sku.sold_count) : 0,
  }
}