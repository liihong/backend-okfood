import { request, getMemberToken, getCourierToken } from '@/utils/api.js'
import { fetchEntryPoster } from '@/utils/homeApi.js'
import { optimizeImageUrl } from '@/utils/imageUrl.js'
import { shouldPromptMemberCardPay, isPaidCardAwaitingSetup } from '@/utils/memberProfile.js'
import { showEntryPosterModal, entryPosterVisible } from '@/utils/entryPosterState.js'

const STORAGE_KEY = 'okfood_entry_poster_shown_v1'

let posterInFlight = false

/** 本机是否已展示过进入海报（非会员仅弹一次） */
function hasEntryPosterShown() {
  try {
    return !!uni.getStorageSync(STORAGE_KEY)
  } catch {
    return false
  }
}

function markEntryPosterShown() {
  try {
    uni.setStorageSync(STORAGE_KEY, '1')
  } catch {
    /* ignore */
  }
}

/** @returns {Promise<boolean>} true=已是会员（已开卡） */
async function resolveIsActiveMember() {
  const token = getMemberToken()
  if (!token) return false
  try {
    const profile = await request('/api/user/me', { method: 'GET' })
    if (!profile || typeof profile !== 'object') return false
    if (isPaidCardAwaitingSetup(profile)) return true
    return !shouldPromptMemberCardPay(profile)
  } catch {
    return false
  }
}

/**
 * 进入小程序时弹出配置海报（未登录或非会员；本机仅弹一次）。
 * @returns {Promise<boolean>} 是否已弹出海报
 */
export async function tryShowEntryPoster() {
  if (posterInFlight) return false
  if (entryPosterVisible.value) return false
  if (getCourierToken()) return false
  if (hasEntryPosterShown()) return false

  posterInFlight = true
  try {
    const isMember = await resolveIsActiveMember()
    if (isMember) return false

    const poster = await fetchEntryPoster()
    const imageUrl = poster?.image_url != null ? String(poster.image_url).trim() : ''
    if (!imageUrl) return false
    const thumb = poster?.image_thumb_url ?? poster?.imageThumbUrl
    const displayUrl = optimizeImageUrl(imageUrl, thumb, 'poster')

    markEntryPosterShown()
    showEntryPosterModal(displayUrl)
    return true
  } catch {
    /* 静默失败，不影响主流程 */
    return false
  } finally {
    posterInFlight = false
  }
}
