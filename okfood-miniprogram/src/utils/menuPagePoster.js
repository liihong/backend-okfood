import { getCourierToken } from '@/utils/api.js'
import { fetchMenuPagePoster } from '@/utils/homeApi.js'
import { entryPosterVisible } from '@/utils/entryPosterState.js'
import { couponReminderVisible } from '@/utils/memberCouponReminderState.js'
import { showMenuPagePosterModal, menuPagePosterVisible } from '@/utils/menuPagePosterState.js'

let posterInFlight = false

/** 等待其他弹窗关闭后再展示菜单页海报 */
function waitForOtherModalsClosed(maxWaitMs = 1200) {
  return new Promise((resolve) => {
    const start = Date.now()
    const tick = () => {
      if (!entryPosterVisible.value && !couponReminderVisible.value) {
        resolve(true)
        return
      }
      if (Date.now() - start >= maxWaitMs) {
        resolve(false)
        return
      }
      setTimeout(tick, 120)
    }
    tick()
  })
}

/**
 * 进入菜单页时弹出配置海报（每次进入均展示；与其他弹窗错开）。
 * @returns {Promise<boolean>} 是否已弹出海报
 */
export async function tryShowMenuPagePoster() {
  if (posterInFlight) return false
  if (menuPagePosterVisible.value) return false
  if (getCourierToken()) return false

  posterInFlight = true
  try {
    const canShow = await waitForOtherModalsClosed()
    if (!canShow || entryPosterVisible.value || couponReminderVisible.value) return false

    const poster = await fetchMenuPagePoster()
    const imageUrl = poster?.image_url != null ? String(poster.image_url).trim() : ''
    if (!imageUrl) return false

    if (entryPosterVisible.value || couponReminderVisible.value) return false

    showMenuPagePosterModal(imageUrl)
    return true
  } catch {
    /* 静默失败，不影响主流程 */
    return false
  } finally {
    posterInFlight = false
  }
}
