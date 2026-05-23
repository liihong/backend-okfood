import { request } from '@/utils/api.js'

/**
 * 续费提醒订阅消息：与后端 .env 中 WX_MINI_SUBSCRIBE_RENEW_TMPL_ID 保持一致。
 * 留空则不在完善资料页拉起授权。
 */
export const RENEW_REMIND_SUBSCRIBE_TMPL_ID = '6B5siPeJo0hpKuYhdy5O_yEiDTEKj3Su_72y3ksBigU'

/**
 * 完善资料保存成功后请求续费提醒订阅；用户同意后通知后端 +1 发送额度。
 * @returns {Promise<boolean>} 是否已成功记录授权额度
 */
export function requestRenewRemindSubscribeAndGrant() {
  if (!RENEW_REMIND_SUBSCRIBE_TMPL_ID) return Promise.resolve(false)
  if (typeof uni.requestSubscribeMessage !== 'function') return Promise.resolve(false)

  return new Promise((resolve) => {
    uni.requestSubscribeMessage({
      tmplIds: [RENEW_REMIND_SUBSCRIBE_TMPL_ID],
      success(res) {
        const st = res && res[RENEW_REMIND_SUBSCRIBE_TMPL_ID]
        if (st !== 'accept') {
          resolve(false)
          return
        }
        request('/api/user/me/subscribe/renew-remind/grant', { method: 'POST' })
          .then(() => resolve(true))
          .catch(() => resolve(false))
      },
      fail() {
        resolve(false)
      },
    })
  })
}
