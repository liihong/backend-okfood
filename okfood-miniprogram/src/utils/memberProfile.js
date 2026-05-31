import { minMemberDeliveryStartYmd } from '@/utils/memberDeliveryDate.js'

/** 与后端 `STUB_MEMBER_NAME` 一致 */
export const MEMBER_STUB_NAME = '待完善'

export const WX_DEFAULT_NICK = '微信用户'

export function isPlaceholderWxProfile(p) {
  if (!p) return true
  const name = String(p.nickName || '').trim()
  const avatar = String(p.avatarUrl || '').trim()
  if (!name || !avatar) return true
  if (name === WX_DEFAULT_NICK) return true
  return false
}

/**
 * 是否有可用的会员展示名（微信昵称、或非占位真实姓名）
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 */
export function hasUsableMemberDisplayName(profile) {
  if (!profile || typeof profile !== 'object') return false
  const nm = (profile.name != null ? String(profile.name) : '').trim()
  const stub = nm === MEMBER_STUB_NAME || nm === ''
  const wn = (profile.wechat_name != null ? String(profile.wechat_name) : '').trim()
  const wxOk = wn !== '' && wn !== WX_DEFAULT_NICK
  return wxOk || (!stub && nm !== '')
}

/** 服务端是否已上传头像 */
export function hasMemberAvatar(profile) {
  if (!profile || typeof profile !== 'object') return false
  const av = profile.avatar_url != null ? String(profile.avatar_url).trim() : ''
  return av !== ''
}

/**
 * 新用户登录后是否须先完善昵称（头像可选，便于客服区分会员）
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 */
export function shouldCompleteMemberProfile(profile) {
  if (!profile || typeof profile !== 'object') return false
  return !hasUsableMemberDisplayName(profile)
}

/** @param {unknown} d */
function ymdFromApiField(d) {
  if (d == null || d === '') return ''
  const s = String(d).trim()
  return s.length >= 10 ? s.slice(0, 10) : ''
}

/**
 * 是否需要引导「完善配送信息」：有余额、非暂停状态下，需补齐起送日与（配送到家时）默认地址
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 */
export function shouldOpenMemberSetup(profile) {
  if (!profile || typeof profile !== 'object') return false
  const balance = Math.max(0, Math.floor(Number(profile.balance) || 0))
  if (balance <= 0) return false
  if (profile.delivery_deferred === true) return false

  const start = ymdFromApiField(profile.delivery_start_date)
  if (!start) return true
  const minD = minMemberDeliveryStartYmd()
  if (start < minD) return true

  if (profile.store_pickup === true) return false

  const addr = profile.address != null ? String(profile.address).trim() : ''
  if (!addr) return true
  return false
}

/**
 * 是否需开卡/续费提示（剩余餐次为 0，与「我的」、资料页开卡区一致）
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 */
export function shouldPromptMemberCardPay(profile) {
  if (!profile || typeof profile !== 'object') return false
  const balance = Math.max(0, Math.floor(Number(profile.balance) || 0))
  return balance <= 0
}

/**
 * 会员卡暂停配送且仍有剩余次数（与后台 delivery_deferred + balance 一致）
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 */
export function isDeliveryPausedWithBalance(profile) {
  if (!profile || typeof profile !== 'object') return false
  const balance = Math.max(0, Math.floor(Number(profile.balance) || 0))
  return profile.delivery_deferred === true && balance > 0
}
