import { ref } from 'vue'

const toastOpen = ref(false)
/** 主标题（单行时也是整段文案） */
const toastTitle = ref('')
/** 副文案（可选，与 iOS 玻璃示意稿一致） */
const toastDetail = ref('')
const toastKind = ref('success')
let toastTimer = 0

const DEFAULT_TITLES = {
  success: '操作成功',
  error: '操作失败',
  warning: '请注意',
  info: '提示',
}

/**
 * 全局轻提示（与 design 约定：玻璃底 + 左侧图标格 + 标题/副文）
 * @param {string} message 主文案；若传入 options 且含 description，则 message 常作副文或可与 description 二选一
 * @param {'success' | 'error' | 'warning' | 'info'} [kind='success']
 * @param {{ title?: string, description?: string }} [options] 可选：显式标题/副文
 */
export function showToast(message, kind = 'success', options) {
  const k =
    kind === 'error' || kind === 'warning' || kind === 'info' || kind === 'success' ? kind : 'success'
  const msg = message != null ? String(message).trim() : ''
  const opt = options && typeof options === 'object' ? options : null
  const explicitTitle = opt?.title != null ? String(opt.title).trim() : ''
  const explicitDesc = opt?.description != null ? String(opt.description).trim() : ''

  if (explicitTitle && explicitDesc) {
    toastTitle.value = explicitTitle
    toastDetail.value = explicitDesc
  } else if (explicitTitle) {
    toastTitle.value = explicitTitle
    toastDetail.value = msg
  } else if (explicitDesc) {
    toastTitle.value = msg || DEFAULT_TITLES[k] || DEFAULT_TITLES.success
    toastDetail.value = explicitDesc
  } else {
    toastTitle.value = msg || DEFAULT_TITLES[k] || DEFAULT_TITLES.success
    toastDetail.value = ''
  }

  toastKind.value = k
  toastOpen.value = true
  window.clearTimeout(toastTimer)
  const duration = k === 'error' ? 3200 : k === 'warning' ? 3000 : 2600
  toastTimer = window.setTimeout(() => {
    toastOpen.value = false
  }, duration)
}

export function useToast() {
  return { toastOpen, toastTitle, toastDetail, toastKind, showToast }
}
