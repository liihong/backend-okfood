import {
  requestOkAlert,
  syncOkAlertHostToCurrentPage,
  isOkAlertHostReadyForCurrentPage,
} from '@/utils/okAlertState.js'

/**
 * 微信原生弹窗兜底：Tab 页 Host 未就绪时保证真机可立即弹出。
 * @param {object} options
 * @returns {Promise<{ confirm?: boolean, cancel?: boolean }>}
 */
function showNativeModal(options = {}) {
  const {
    title = '',
    content = '',
    showCancel = true,
    cancelText = '取消',
    confirmText = '确定',
    confirmColor,
    success,
    fail,
  } = options

  return new Promise((resolve) => {
    uni.showModal({
      title: String(title || ''),
      content: String(content || ''),
      showCancel: !!showCancel,
      cancelText: cancelText || '取消',
      confirmText: confirmText || '确定',
      confirmColor: confirmColor || (showCancel ? '#73B054' : undefined),
      success: (res) => {
        const out = { confirm: !!res.confirm, cancel: !!res.cancel }
        if (typeof success === 'function') success(out)
        resolve(out)
      },
      fail: (e) => {
        if (typeof fail === 'function') fail()
        resolve({ confirm: false, cancel: true })
        console.warn('[showOkAlert] uni.showModal fail', e)
      },
    })
  })
}

/**
 * 自定义提醒卡片，API 对齐 uni.showModal。
 * Host 不可用时自动降级为 uni.showModal（真机 Tab 页必需）。
 * @param {object} options
 * @param {string} [options.title]
 * @param {string} [options.content]
 * @param {boolean} [options.showCancel=true]
 * @param {string} [options.cancelText='取消']
 * @param {string} [options.confirmText='确定']
 * @param {string} [options.confirmColor] 兼容 uni.showModal，#ff3e3e / #b91c1c 等视为危险确认
 * @param {'default'|'success'|'warning'} [options.tone]
 * @param {boolean} [options.maskClosable=false]
 * @param {(res: { confirm?: boolean, cancel?: boolean }) => void} [options.success]
 * @param {() => void} [options.fail]
 */
export function showOkAlert(options = {}) {
  const {
    title = '',
    content = '',
    showCancel = true,
    cancelText = '取消',
    confirmText = '确定',
    confirmColor,
    tone = 'default',
    maskClosable = false,
    success,
    fail,
  } = options

  const confirmDanger =
    typeof confirmColor === 'string' &&
    /(?:ff3e3e|b91c1c|dd524d|f43f5e|ef4444)/i.test(confirmColor)

  const payload = {
    title: String(title || ''),
    content: String(content || ''),
    showCancel: !!showCancel,
    cancelText: cancelText || '取消',
    confirmText: confirmText || '确定',
    confirmDanger,
    tone,
    maskClosable: !!maskClosable,
  }

  syncOkAlertHostToCurrentPage()
  if (!isOkAlertHostReadyForCurrentPage()) {
    return showNativeModal(options)
  }

  try {
    return requestOkAlert(payload).then((res) => {
      if (res == null) {
        return showNativeModal(options)
      }
      if (typeof success === 'function') success(res)
      return res
    })
  } catch (e) {
    if (typeof fail === 'function') fail()
    return showNativeModal(options)
  }
}
