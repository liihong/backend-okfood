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

function hasNonEmptyField(v) {
  return v != null && String(v).trim() !== ''
}

/**
 * 是否需要引导「完善资料」：占位姓名、缺展示用昵称、或既未选起送日又未选「暂停配送」
 * 与「开卡/支付」解耦，不因剩余次数为 0 而强制进资料页（购卡在独立模块中完成）。
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 */
export function shouldOpenMemberSetup(profile) {
  if (!profile || typeof profile !== 'object') return true
  const nm = (profile.name != null ? String(profile.name) : '').trim()
  const stub = nm === MEMBER_STUB_NAME || nm === ''
  const wn = (profile.wechat_name != null ? String(profile.wechat_name) : '').trim()
  const wxOk = wn !== '' && wn !== WX_DEFAULT_NICK
  const hasUsableName = wxOk || (!stub && nm !== '')
  const deferred = profile.delivery_deferred === true
  const noDeliveryStart =
    !hasNonEmptyField(profile.delivery_start_date) && !deferred
  if (!hasUsableName || noDeliveryStart) return true
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
