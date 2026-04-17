/**
 * 与后端 .env 中 WX_MINI_SUBSCRIBE_DELIVERY_TMPL_ID 保持一致。
 * 留空则不在前端拉起订阅授权（服务端也不会下发）。
 */
export const DELIVERY_SUBSCRIBE_TMPL_ID = ''

let lastDeliverySubscribePromptKey = ''

/**
 * 每天最多弹一次订阅授权，避免打扰；用户同意后，配送员确认送达时服务端才可下发一条对应模板消息。
 */
export function requestDeliverySubscribeOncePerDay() {
  if (!DELIVERY_SUBSCRIBE_TMPL_ID) return
  try {
    const key = new Date().toISOString().slice(0, 10)
    if (lastDeliverySubscribePromptKey === key) return
    lastDeliverySubscribePromptKey = key
    if (typeof uni.requestSubscribeMessage !== 'function') return
    uni.requestSubscribeMessage({
      tmplIds: [DELIVERY_SUBSCRIBE_TMPL_ID],
      fail() {
        /* 用户拒绝或基础库限制：静默 */
      },
    })
  } catch {
    /* noop */
  }
}
