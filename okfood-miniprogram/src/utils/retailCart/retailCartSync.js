/**
 * 用 SKU  lookup 刷新购物车价格/库存，剔除失效商品。
 */
import { fetchRetailSkuLookup } from '@/utils/catalogApi.js'
import { readCartItemsRaw, writeCartItemsRaw } from './retailCartStorage.js'

/** @returns {Promise<{ items: import('./retailCartTypes.js').RetailCartItem[], removed: string[] }>} */
export async function syncCartWithRetailMenu() {
  const cart = readCartItemsRaw()
  if (!cart.length) return { items: [], removed: [] }

  const lookup = await fetchRetailSkuLookup()

  const removed = []
  const next = []
  for (const row of cart) {
    const pid = Number(row.retailProductId)
    const live = lookup[String(pid)] || lookup[pid]
    if (!live) {
      removed.push(row.title || '商品')
      continue
    }
    const remain = live.stock_remaining != null ? Number(live.stock_remaining) : null
    if (live.stock_limited && remain != null && remain <= 0) {
      removed.push(row.title || '商品')
      continue
    }
    let qty = Number(row.quantity) || 1
    if (remain != null && qty > remain) qty = Math.max(1, remain)
    next.push({
      ...row,
      spuId: live.spu_id != null ? Number(live.spu_id) : row.spuId,
      spuTitle: live.spu_title != null ? String(live.spu_title) : row.spuTitle,
      specLabel: live.spec_label != null ? String(live.spec_label) : row.specLabel,
      title: String(live.title || row.title || '商品'),
      unitPriceYuan: live.unit_price_yuan != null ? String(live.unit_price_yuan) : row.unitPriceYuan,
      listPriceYuan: live.list_price_yuan != null ? String(live.list_price_yuan) : row.listPriceYuan,
      coverImageUrl: live.cover_image_url || row.coverImageUrl,
      stockRemaining: remain,
      stockLimited: !!live.stock_limited,
      soldCount: live.sold_count != null ? Number(live.sold_count) : 0,
      quantity: qty,
    })
  }
  writeCartItemsRaw(next)
  return { items: next, removed }
}
