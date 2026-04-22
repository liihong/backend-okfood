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
 * 是否需要引导「完善资料」页：占位姓名、缺展示用昵称、未选套餐意向或未选起送日
 * 说明：`name` 与 `wechat_name` 任一可用即可（后台常只写 name）；头像可选，与资料页文案一致。
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 */
export function shouldOpenMemberSetup(profile) {
  if (!profile || typeof profile !== 'object') return true
  const nm = (profile.name != null ? String(profile.name) : '').trim()
  const stub = nm === MEMBER_STUB_NAME || nm === ''
  const wn = (profile.wechat_name != null ? String(profile.wechat_name) : '').trim()
  const wxOk = wn !== '' && wn !== WX_DEFAULT_NICK
  const hasUsableName = wxOk || (!stub && nm !== '')
  const noDeliveryStart = !hasNonEmptyField(profile.delivery_start_date)
  if (!hasUsableName || noDeliveryStart) return true
  const balance = Math.max(0, Math.floor(Number(profile.balance) || 0))
  // 有剩余次数：仅需资料与起送日，不必再购卡
  if (balance > 0) return false
  // 无剩余次数：须进入完善页选卡并支付（或续卡），不依赖 plan_type 避免「只保存意向未付款」被当成已完成
  return true
}
