import { request } from '@/utils/api.js'

import { optimizeImageUrl } from '@/utils/imageUrl.js'



/**

 * @typedef {{ id: number, title: string, subtitle?: string | null, cover_image_url?: string | null, price_min_yuan?: string | null, price_max_yuan?: string | null, has_multi_sku?: boolean, stock_limited?: boolean, stock_remaining?: number | null }} RetailSpuPublic

 * @typedef {{ id: number, name: string, sort_order: number, products: RetailSpuPublic[] }} RetailCategoryPublic

 * @returns {Promise<RetailCategoryPublic[]>}

 */

export async function fetchRetailMenu() {

  const raw = await request('/api/catalog/retail-menu', { method: 'GET', retry: 1 })

  return Array.isArray(raw) ? raw : []

}



/**

 * @param {number} spuId

 * @returns {Promise<Record<string, unknown> | null>}

 */

export async function fetchRetailSpuDetail(spuId) {

  const id = Number(spuId)

  if (!Number.isFinite(id) || id < 1) return null

  try {

    return await request(`/api/catalog/retail-spu/${id}`, { method: 'GET', retry: 1 })

  } catch {

    return null

  }

}



export async function fetchRetailSkuDetail(skuId) {
  const id = Number(skuId)
  if (!Number.isFinite(id) || id < 1) return null
  try {
    return await request(`/api/catalog/retail-sku/${id}`, { method: 'GET', retry: 1 })
  } catch {
    return null
  }
}



/** @returns {Promise<Record<string, Record<string, unknown>>>} */

export async function fetchRetailSkuLookup() {

  const raw = await request('/api/catalog/retail-sku-lookup', { method: 'GET', retry: 1 })

  return raw && typeof raw === 'object' ? raw : {}

}



function formatPriceLabel(minYuan, maxYuan) {

  const lo = minYuan != null && String(minYuan).trim() !== '' ? Number(minYuan) : null

  const hi = maxYuan != null && String(maxYuan).trim() !== '' ? Number(maxYuan) : null

  if (lo == null || !Number.isFinite(lo)) return null

  if (hi == null || !Number.isFinite(hi) || hi === lo) return lo

  return lo

}



/** @param {RetailSpuPublic} p */

export function mapRetailSpuItem(p) {

  const id = p?.id != null ? Number(p.id) : 0

  const priceMin = formatPriceLabel(p?.price_min_yuan, p?.price_max_yuan)

  const priceMax =

    p?.price_max_yuan != null && String(p.price_max_yuan).trim() !== ''

      ? Number(p.price_max_yuan)

      : priceMin

  const showFrom = p?.has_multi_sku && priceMin != null && priceMax != null && priceMax > priceMin

  return {

    rowKey: `retail-spu-${id}`,

    retailSpuId: id,

    isRetail: true,

    name: typeof p?.title === 'string' ? p.title : '商品',

    ingredients: typeof p?.subtitle === 'string' ? p.subtitle.trim() : '',

    price: priceMin,
    priceSuffix: showFrom ? '起' : '',
    listPrice: null,

    img: optimizeImageUrl(

      typeof p?.cover_image_url === 'string' ? p.cover_image_url : '',

      typeof p?.cover_image_thumb_url === 'string' ? p.cover_image_thumb_url : null,

      'list',

    ),

    imgOriginal: typeof p?.cover_image_url === 'string' ? p.cover_image_url : '',

    stockRemaining: p?.stock_remaining != null ? Number(p.stock_remaining) : null,

    stockLimited: !!p?.stock_limited,

    hasMultiSku: !!p?.has_multi_sku,

  }

}



/** @deprecated 兼容旧调用名 */

export const mapRetailProductItem = mapRetailSpuItem

