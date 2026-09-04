import { request } from '@/utils/api.js'

import { optimizeImageUrl } from '@/utils/imageUrl.js'



/**

 * @returns {Promise<{

 *   store_id: number,

 *   store_name?: string | null,

 *   store_logo_url?: string | null,

 *   store_logo_thumb_url?: string | null,

 *   store_contact_phone?: string | null,

 *   store_lng?: number | null,

 *   store_lat?: number | null,

 *   store_pickup_address?: string | null,

 *   base_delivery_fee_yuan?: number | null,

 * } | null>}

 */

export async function fetchStoreInfo() {

  const raw = await request('/api/home/store-info', { method: 'GET', retry: 1 })

  if (!raw || typeof raw !== 'object') return null

  return raw

}



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

/**
 * @typedef {{
 *   spu_id: number,
 *   store_name: string,
 *   store_logo_url?: string | null,
 *   recommend_text?: string | null,
 *   title: string,
 *   subtitle?: string | null,
 *   price_yuan?: string | number | null,
 *   cover_image_url?: string | null,
 *   wxacode_base64: string,
 *   scene: string,
 * }} RetailSharePosterPayload
 */

/**
 * @param {number} spuId
 * @param {'release' | 'trial' | 'develop'} [envVersion]
 * @returns {Promise<RetailSharePosterPayload>}
 */
export async function fetchRetailSharePoster(spuId, envVersion = 'release') {
  const id = Number(spuId)
  if (!Number.isFinite(id) || id < 1) {
    throw new Error('商品无效')
  }
  const env = envVersion === 'trial' || envVersion === 'develop' ? envVersion : 'release'
  return request(`/api/catalog/retail-spu/${id}/share-poster?env_version=${encodeURIComponent(env)}`, {
    method: 'GET',
    retry: 1,
  })
}

