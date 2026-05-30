/** 与后端 app/services/sf_open/user_messages.py 文案保持一致 */

export const SF_MSG_BALANCE =
  '顺丰预付费账户余额不足，请登录顺丰同城商户后台充值后再推单'

export function isSfBalanceMessage(message) {
  const m = String(message || '').trim()
  if (!m) return false
  return m.includes('余额不足') || m.includes('预付费') || m.includes('充值后再推单')
}

/**
 * 配送大表 / 批量推顺丰：根据接口 data 弹出合适提示
 * @param {object} data 接口 data 字段
 * @param {(msg: string, kind: string) => void} showToast
 * @param {{ successText?: string, formatFailLine?: (row: object) => string }} [opts]
 */
export function toastSfPushBatchOutcome(data, showToast, opts = {}) {
  const successText = opts.successText || '已全部提交'
  const formatFailLine =
    opts.formatFailLine || ((f) => `${String(f.stop_id || '').slice(0, 8)}: ${f.message || ''}`)

  const hint = data && typeof data.hint === 'string' ? data.hint.trim() : ''
  const results = Array.isArray(data?.results) ? data.results : []
  const fail = results.filter((x) => x && !x.ok)

  if (hint) {
    const okCount = results.filter((x) => x && x.ok).length
    if (okCount > 0) {
      showToast(`${hint}（另有 ${okCount} 单已成功提交）`, 'warning')
    } else {
      showToast(hint, 'error')
    }
    return
  }

  if (!fail.length) {
    showToast(successText, 'success')
    return
  }

  if (fail.every((f) => isSfBalanceMessage(f.message))) {
    showToast(SF_MSG_BALANCE, 'error')
    return
  }

  const msg = fail.map(formatFailLine).join('；')
  showToast(`部分失败：${msg}`, 'error')
}

/** 单笔推顺丰 / 重试：优先展示余额不足文案 */
export function toastSfPushError(message, showToast) {
  const m = String(message || '').trim()
  if (isSfBalanceMessage(m)) {
    showToast(SF_MSG_BALANCE, 'error')
    return
  }
  showToast(m || '推单失败', 'error')
}
