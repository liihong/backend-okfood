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

/**
 * 是否需要引导「完善资料」：仅检查头像/称呼（起送日、配送方式在资料与开卡流程中另行设置）
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 */
export function shouldOpenMemberSetup(profile) {
  if (!profile || typeof profile !== 'object') return true
  return !hasUsableMemberDisplayName(profile)
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
