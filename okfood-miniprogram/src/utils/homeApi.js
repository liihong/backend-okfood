import { request } from '@/utils/api.js'

/**
 * @returns {Promise<Array<{ id: number, image_url: string, link_type: string, link_target?: string | null }>>}
 */
export async function fetchHomeBanners() {
  const raw = await request('/api/home/banners', { method: 'GET', retry: 1 })
  return Array.isArray(raw) ? raw : []
}

/**
 * @returns {Promise<Array<{ id: number, name: string, meals_grant: number, sale_price_yuan?: string | null }>>}
 */
export async function fetchHomeMembershipCards() {
  const raw = await request('/api/home/membership-card-templates', { method: 'GET', retry: 1 })
  return Array.isArray(raw) ? raw : []
}

/**
 * @param {{ link_type?: string, link_target?: string | null }} banner
 * @param {string} [todayYmd] 供餐日，dish 跳转时使用
 */
export function navigateHomeBanner(banner, todayYmd) {
  if (!banner || typeof banner !== 'object') return
  const type = String(banner.link_type || 'none').toLowerCase()
  const target = String(banner.link_target || '').trim()
  if (type === 'none' || !type) return

  if (type === 'dish') {
    if (!target) {
      uni.showToast({ title: '跳转配置无效', icon: 'none' })
      return
    }
    const q = [`dish_id=${encodeURIComponent(target)}`]
    const svc = String(todayYmd || '').trim()
    if (svc) q.push(`service_date=${encodeURIComponent(svc)}`)
    uni.navigateTo({ url: `/packageOrder/pages/detail/detail?${q.join('&')}` })
    return
  }

  if (type === 'tab') {
    if (!target) {
      uni.showToast({ title: '跳转配置无效', icon: 'none' })
      return
    }
    const path = target.startsWith('/') ? target : `/${target}`
    uni.switchTab({ url: path })
    return
  }

  if (type === 'webview') {
    if (!target.startsWith('https://')) {
      uni.showToast({ title: '外链无效', icon: 'none' })
      return
    }
    uni.navigateTo({
      url: `/pages/webview/index?url=${encodeURIComponent(target)}`,
    })
    return
  }

  if (type === 'member_card') {
    if (!target || !/^\d+$/.test(target)) {
      uni.showToast({ title: '跳转配置无效', icon: 'none' })
      return
    }
    uni.navigateTo({
      url: `/packageUser/pages/membershipCardDetail/membershipCardDetail?templateId=${encodeURIComponent(target)}`,
    })
  }
}
