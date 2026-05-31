import { request, getMemberToken } from '@/utils/api.js'
import { WX_DEFAULT_NICK } from '@/utils/memberProfile.js'

/** 微信头像昵称本地缓存前缀（按手机号分 key） */
export const WX_PROFILE_PREFIX = 'okfood_wx_profile'

/** @param {string} [phone] */
export function wxProfileStorageKey(phone) {
  const p = phone || uni.getStorageSync('memberPhone') || ''
  return p ? `${WX_PROFILE_PREFIX}:${p}` : WX_PROFILE_PREFIX
}

/**
 * 读取本地微信头像/昵称缓存
 * @param {string} [phone]
 * @returns {{ nickName: string, avatarUrl: string } | null}
 */
export function loadWxProfile(phone) {
  const key = wxProfileStorageKey(phone)
  try {
    let raw = uni.getStorageSync(key)
    if (
      !raw &&
      typeof localStorage !== 'undefined' &&
      typeof localStorage.getItem === 'function'
    ) {
      const s = localStorage.getItem(key)
      raw = s ? JSON.parse(s) : null
    }
    if (!raw) return null
    const p = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!p || typeof p !== 'object') return null
    return {
      nickName: p.nickName != null ? String(p.nickName) : '',
      avatarUrl: p.avatarUrl != null ? String(p.avatarUrl) : '',
    }
  } catch {
    return null
  }
}

/**
 * 持久化微信头像/昵称到本地
 * @param {{ nickName?: string, avatarUrl?: string }} p
 * @param {string} [phone]
 */
export function persistWxProfile(p, phone) {
  const key = wxProfileStorageKey(phone)
  const payload = { nickName: p.nickName || '', avatarUrl: p.avatarUrl || '' }
  uni.setStorageSync(key, payload)
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, JSON.stringify(payload))
    }
  } catch {
    /* 小程序无 localStorage 时忽略 */
  }
}

/**
 * 将会员微信昵称/头像同步到服务端 members.wechat_name、avatar_url
 * @param {{ wechat_name?: string, avatar_url?: string }} partial
 * @param {{ showErrorToast?: boolean }} [options]
 */
export async function pushWechatProfileToServer(partial, options = {}) {
  const { showErrorToast = true } = options
  if (!getMemberToken()) return
  const body = {}
  if (partial.wechat_name !== undefined) body.wechat_name = partial.wechat_name
  if (partial.avatar_url !== undefined) body.avatar_url = partial.avatar_url
  if (Object.keys(body).length === 0) return
  try {
    await request('/api/user/profile', { method: 'PATCH', data: body })
  } catch (err) {
    console.warn('pushWechatProfileToServer', err)
    if (showErrorToast) {
      uni.showToast({ title: err?.message || '资料同步失败', icon: 'none' })
      return
    }
    throw err
  }
}

/** @param {string} nick */
export function isValidWxNick(nick) {
  const n = String(nick || '').trim()
  return n !== '' && n !== WX_DEFAULT_NICK
}
