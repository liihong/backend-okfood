/**
 * 商城零售本地购物车（不同步服务端）。
 * key 按 storeId + memberId 隔离。
 */

import { getMemberStoreId } from '@/utils/api.js'

const STORAGE_PREFIX = 'okfood_retail_cart_'
const MAX_SKUS = 20
const MAX_QTY = 50

/** @param {string} [memberId] */
function cartStorageKeyFor(memberId) {
  const storeId = getMemberStoreId() || '0'
  const mid = String(memberId ?? '').trim()
  if (mid) return `${STORAGE_PREFIX}${storeId}_${mid}`
  let cached = ''
  try {
    cached = String(uni.getStorageSync('memberId') || '').trim()
  } catch {
    cached = ''
  }
  return `${STORAGE_PREFIX}${storeId}_${cached || 'guest'}`
}

/** @returns {string} */
function cartStorageKey() {
  return cartStorageKeyFor('')
}

/**
 * @param {number} qty
 * @param {import('./retailCartTypes.js').RetailCartProductInput | import('./retailCartTypes.js').RetailCartItem} product
 */
function capQtyByStock(qty, product) {
  let next = Math.min(MAX_QTY, Math.max(0, Math.floor(Number(qty) || 0)))
  if (product?.stockLimited && product?.stockRemaining != null) {
    const remain = Math.max(0, Math.floor(Number(product.stockRemaining)))
    next = Math.min(next, remain)
  }
  return next
}

/** @returns {import('./retailCartTypes.js').RetailCartItem[]} */
export function readCartItemsRaw() {
  try {
    const raw = uni.getStorageSync(cartStorageKey())
    return Array.isArray(raw) ? raw : []
  } catch {
    return []
  }
}

/** @param {import('./retailCartTypes.js').RetailCartItem[]} items */
export function writeCartItemsRaw(items) {
  uni.setStorageSync(cartStorageKey(), items)
}

/**
 * 登录后将 guest 购物车合并到会员 key（同 SKU 累加数量，受库存/上限约束）。
 * @param {string|number} memberId
 */
export function mergeGuestCartAfterLogin(memberId) {
  const mid = String(memberId ?? '').trim()
  if (!mid) return
  const storeId = getMemberStoreId() || '0'
  const guestKey = `${STORAGE_PREFIX}${storeId}_guest`
  const memberKey = `${STORAGE_PREFIX}${storeId}_${mid}`
  if (guestKey === memberKey) return

  let guestItems = []
  try {
    const raw = uni.getStorageSync(guestKey)
    guestItems = Array.isArray(raw) ? raw : []
  } catch {
    guestItems = []
  }
  if (!guestItems.length) return

  let memberItems = []
  try {
    const raw = uni.getStorageSync(memberKey)
    memberItems = Array.isArray(raw) ? raw : []
  } catch {
    memberItems = []
  }

  /** @type {Map<number, import('./retailCartTypes.js').RetailCartItem>} */
  const merged = new Map()
  for (const row of memberItems) {
    const pid = Number(row.retailProductId)
    if (Number.isFinite(pid) && pid > 0) merged.set(pid, { ...row })
  }
  for (const row of guestItems) {
    const pid = Number(row.retailProductId)
    if (!Number.isFinite(pid) || pid < 1) continue
    const prev = merged.get(pid)
    const combined = capQtyByStock((Number(prev?.quantity) || 0) + (Number(row.quantity) || 0), {
      stockLimited: row.stockLimited ?? prev?.stockLimited,
      stockRemaining: row.stockRemaining ?? prev?.stockRemaining,
    })
    if (combined < 1) continue
    merged.set(pid, {
      ...(prev || {}),
      ...row,
      quantity: combined,
    })
  }

  const next = Array.from(merged.values()).slice(0, MAX_SKUS)
  uni.setStorageSync(memberKey, next)
  try {
    uni.removeStorageSync(guestKey)
  } catch {
    /* ignore */
  }
  try {
    uni.$emit('retail-cart-changed')
  } catch {
    /* ignore */
  }
}

/**
 * @param {import('./retailCartTypes.js').RetailCartProductInput} product
 * @param {number} [delta=1]
 */
export function addCartItem(product, delta = 1) {
  const pid = Number(product?.retailProductId)
  if (!Number.isFinite(pid) || pid < 1) return { ok: false, msg: '商品无效' }
  const add = Math.max(1, Math.floor(Number(delta) || 1))
  const items = readCartItemsRaw()
  const idx = items.findIndex((x) => Number(x.retailProductId) === pid)
  if (idx < 0 && items.length >= MAX_SKUS) {
    return { ok: false, msg: `购物车最多 ${MAX_SKUS} 种商品` }
  }
  const prevQty = idx >= 0 ? Number(items[idx].quantity) || 0 : 0
  const stockInfo = {
    stockLimited: product.stockLimited ?? items[idx]?.stockLimited,
    stockRemaining: product.stockRemaining ?? items[idx]?.stockRemaining,
  }
  if (stockInfo.stockLimited && stockInfo.stockRemaining != null && Number(stockInfo.stockRemaining) <= 0) {
    return { ok: false, msg: '商品已售罄' }
  }
  const nextQty = capQtyByStock(prevQty + add, stockInfo)
  if (nextQty < 1) {
    return { ok: false, msg: '库存不足' }
  }
  if (nextQty <= prevQty && add > 0) {
    return { ok: false, msg: '已达库存上限' }
  }
  const row = {
    retailProductId: pid,
    spuId: product.spuId != null ? Number(product.spuId) : items[idx]?.spuId,
    spuTitle: product.spuTitle || items[idx]?.spuTitle || '',
    specLabel: product.specLabel || items[idx]?.specLabel || '',
    title: String(product.title || product.name || '商品'),
    unitPriceYuan: product.unitPriceYuan != null ? String(product.unitPriceYuan) : null,
    listPriceYuan: product.listPriceYuan != null ? String(product.listPriceYuan) : null,
    coverImageUrl: product.coverImageUrl || product.imgOriginal || product.img || '',
    stockRemaining: product.stockRemaining != null ? Number(product.stockRemaining) : items[idx]?.stockRemaining ?? null,
    stockLimited: !!product.stockLimited || !!items[idx]?.stockLimited,
    soldCount: product.soldCount != null ? Number(product.soldCount) : items[idx]?.soldCount ?? 0,
    quantity: nextQty,
    addedAt: Date.now(),
  }
  if (idx >= 0) items[idx] = { ...items[idx], ...row }
  else items.push(row)
  writeCartItemsRaw(items)
  return { ok: true, quantity: nextQty }
}

/** @param {number} productId @param {number} quantity */
export function setCartItemQuantity(productId, quantity) {
  const pid = Math.floor(Number(productId))
  const qty = Math.floor(Number(quantity))
  const items = readCartItemsRaw()
  const idx = items.findIndex((x) => Number(x.retailProductId) === pid)
  if (idx < 0) return { ok: false, msg: '商品不在购物车' }
  if (qty < 1) {
    items.splice(idx, 1)
    writeCartItemsRaw(items)
    return { ok: true, quantity: 0 }
  }
  const capped = capQtyByStock(qty, items[idx])
  if (capped < 1) {
    items.splice(idx, 1)
    writeCartItemsRaw(items)
    return { ok: true, quantity: 0, msg: '库存不足，已移除' }
  }
  items[idx].quantity = capped
  writeCartItemsRaw(items)
  return { ok: true, quantity: capped, capped: capped < qty }
}

/** @param {number} productId */
export function removeCartItem(productId) {
  setCartItemQuantity(productId, 0)
}

export function clearCart() {
  writeCartItemsRaw([])
}

export function getCartCount() {
  return readCartItemsRaw().reduce((sum, it) => sum + (Number(it.quantity) || 0), 0)
}

export function getCartSubtotalText() {
  const total = readCartItemsRaw().reduce((sum, it) => {
    const p = Number(it.unitPriceYuan)
    const q = Number(it.quantity) || 0
    if (!Number.isFinite(p) || q < 1) return sum
    return sum + p * q
  }, 0)
  return total.toFixed(2)
}

/** @returns {import('./retailCartTypes.js').RetailCartItem[]} */
export function getCartItems() {
  return readCartItemsRaw()
}

export const RETAIL_CART_LIMITS = { MAX_SKUS, MAX_QTY }
