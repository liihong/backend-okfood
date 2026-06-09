import { request } from '@/utils/api.js'

/**
 * @returns {Promise<{ store_id: number, store_name?: string | null, store_logo_url?: string | null, store_contact_phone?: string | null } | null>}
 */
export async function fetchStoreInfo() {
  const raw = await request('/api/home/store-info', { method: 'GET', retry: 1 })
  if (!raw || typeof raw !== 'object') return null
  return raw
}

/**
 * @typedef {{ id: number, title: string, subtitle?: string | null, description?: string | null, unit_price_yuan?: string | null, list_price_yuan?: string | null, cover_image_url?: string | null }} RetailProductPublic
 * @typedef {{ id: number, name: string, sort_order: number, products: RetailProductPublic[] }} RetailCategoryPublic
 * @returns {Promise<RetailCategoryPublic[]>}
 */
export async function fetchRetailMenu() {
  const raw = await request('/api/catalog/retail-menu', { method: 'GET', retry: 1 })
  return Array.isArray(raw) ? raw : []
}

/** @param {RetailProductPublic} p */
export function mapRetailProductItem(p) {
  const id = p?.id != null ? Number(p.id) : 0
  const desc =
    (typeof p?.subtitle === 'string' && p.subtitle.trim()) ||
    (typeof p?.description === 'string' && p.description.trim()) ||
    ''
  return {
    rowKey: `retail-${id}`,
    retailProductId: id,
    isRetail: true,
    name: typeof p?.title === 'string' ? p.title : '商品',
    ingredients: desc,
    price: p?.unit_price_yuan,
    listPrice: p?.list_price_yuan,
    img: typeof p?.cover_image_url === 'string' ? p.cover_image_url : '',
  }
}
