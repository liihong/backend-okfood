import { requestOkAlert } from '@/utils/okAlertState.js'

/**
 * 自定义提醒卡片，API 对齐 uni.showModal。
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

  try {
    const p = requestOkAlert(payload)
    p.then((res) => {
      if (typeof success === 'function') success(res)
    })
    return p
  } catch (e) {
    if (typeof fail === 'function') fail()
    throw e
  }
}
