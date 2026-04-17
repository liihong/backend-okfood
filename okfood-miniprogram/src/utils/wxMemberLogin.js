import { request } from './api.js'

function normalizeCnPhone(raw) {
  if (raw == null || raw === '') return ''
  let d = String(raw).replace(/\D/g, '')
  if (d.startsWith('86') && d.length === 13) d = d.slice(2)
  return /^1[3-9]\d{9}$/.test(d) ? d : ''
}

/**
 * 从登录接口 JSON 取 11 位手机号（浅层字段 + user/member 嵌套）
 */
function pickPhoneFromLoginData(data) {
  const tryKeys = (obj) => {
    if (!obj || typeof obj !== 'object') return ''
    return (
      normalizeCnPhone(obj.phone) ||
      normalizeCnPhone(obj.mobile) ||
      normalizeCnPhone(obj.memberPhone) ||
      normalizeCnPhone(obj.member_phone) ||
      ''
    )
  }
  let phone = tryKeys(data)
  if (!phone) {
    const nest = data.user || data.member
    phone = tryKeys(nest)
  }
  return phone || ''
}

/**
 * 启动时调用：本地已有 token 但 memberPhone 丢失时，拉取 /api/user/me 补全（JWT sub 为 members.id，不再含手机号）。
 */
export async function ensureMemberPhoneFromStoredToken() {
  try {
    const token = uni.getStorageSync('okfood_member_token') || ''
    if (!token) return
    const existing = uni.getStorageSync('memberPhone') || ''
    if (existing) return
    const profile = await request('/api/user/me', { method: 'GET' })
    const p = profile?.phone != null ? String(profile.phone).replace(/\D/g, '') : ''
    if (/^1[3-9]\d{9}$/.test(p)) {
      uni.setStorageSync('memberPhone', p)
    }
    if (profile?.id != null) {
      uni.setStorageSync('memberId', String(profile.id))
    }
  } catch {
    /*忽略 */
  }
}

/** 微信授权登录后：写入 token；有手机号时写 memberPhone（展示用，档案以 GET /api/user/me 为准） */
export function applyWxLoginResponse(data) {
  if (!data || typeof data !== 'object') {
    throw new Error('登录响应异常')
  }
  const token = data.access_token || data.accessToken || data.token
  if (!token) {
    throw new Error('未返回 token')
  }
  uni.setStorageSync('okfood_member_token', token)

  const phone = pickPhoneFromLoginData(data)
  if (phone) {
    uni.setStorageSync('memberPhone', phone)
  }
}

export function hasWxPhoneAuthDetail(detail) {
  if (!detail || typeof detail !== 'object') return false
  return !!(detail.code || (detail.encryptedData && detail.iv))
}

/**
 * uni.login 取 js_code + 用户授权手机号的 detail，换会员 token。
 */
/**
 * 已登录会员：用当前小程序会话绑定 wx_mini_openid（单次点餐支付等依赖服务端存有 openid）。
 */
export async function syncWxMiniOpenidFromLogin() {
  const loginRes = await new Promise((resolve, reject) => {
    uni.login({ provider: 'weixin', success: resolve, fail: reject })
  })
  const jsCode = loginRes.code
  if (!jsCode) {
    throw new Error('未取得微信登录 code')
  }
  return request('/api/user/wx/mini/sync-openid', { method: 'POST', data: { js_code: jsCode } })
}

export async function wxMiniMemberLogin(phoneAuthDetail) {
  const loginRes = await new Promise((resolve, reject) => {
    uni.login({ provider: 'weixin', success: resolve, fail: reject })
  })
  const jsCode = loginRes.code
  if (!jsCode) {
    throw new Error('未取得微信登录 code')
  }

  const body = { js_code: jsCode }
  if (typeof phoneAuthDetail === 'string' && phoneAuthDetail) {
    body.phone_code = phoneAuthDetail
  } else if (phoneAuthDetail?.code) {
    body.phone_code = phoneAuthDetail.code
  } else if (phoneAuthDetail?.encryptedData && phoneAuthDetail?.iv) {
    body.encrypted_data = phoneAuthDetail.encryptedData
    body.iv = phoneAuthDetail.iv
  } else {
    throw new Error('未收到手机号授权')
  }

  return request('/api/user/wx/mini/login', { method: 'POST', data: body })
}

/**
 * 登录并落库 token、手机号；若已写入 memberPhone，立即 GET /api/user/me 拉会员档案。
 */
export async function wxMiniMemberLoginAndStore(phoneAuth) {
  const data = await wxMiniMemberLogin(phoneAuth)
  applyWxLoginResponse(data)
  try {
    const profile = await request('/api/user/me', { method: 'GET' })
    const p = profile?.phone != null ? String(profile.phone).replace(/\D/g, '') : ''
    if (/^1[3-9]\d{9}$/.test(p)) {
      uni.setStorageSync('memberPhone', p)
    }
    if (profile?.id != null) {
      uni.setStorageSync('memberId', String(profile.id))
    }
    return { login: data, profile }
  } catch {
    return { login: data, profile: null }
  }
}
