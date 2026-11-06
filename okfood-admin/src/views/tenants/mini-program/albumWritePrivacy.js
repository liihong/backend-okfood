/**
 * 相册（仅写入）隐私用途。
 * 文案与后端 ALBUM_WRITE_ONLY_PRIVACY_TEXT 保持一致。
 * 微信授权弹窗会自动加上「为了」，这里不再写「用于」。
 */
export const ALBUM_WRITE_ONLY_PRIVACY_KEY = 'AlbumWriteOnly'

export const ALBUM_WRITE_ONLY_PRIVACY_TEXT =
  '保存订单核销二维码、分享海报图片到用户相册，仅写入相册，不会读取相册内其他照片、视频'

/** @type {Record<string, string>} */
export const PRIVACY_KEY_LABELS = {
  PhoneNumber: '手机号',
  Location: '位置信息',
  ChooseLocation: '选中的位置信息',
  UserInfo: '用户信息（微信昵称、头像）',
  AlbumWriteOnly: '相册（仅写入）权限',
  Album: '选中的照片或视频信息',
  Camera: '摄像头',
  Clipboard: '剪切板',
}

/**
 * @param {Array<{ privacy_key?: string, privacy_text?: string }> | null | undefined} settingList
 * @returns {Array<{ privacy_key: string, label: string, privacy_text: string, configured: boolean, isAlbum: boolean }>}
 */
export function buildPrivacyDisplayRows(settingList) {
  const remote = Array.isArray(settingList) ? settingList : []
  /** @type {Map<string, string>} */
  const textByKey = new Map()
  /** @type {string[]} */
  const order = []
  for (const item of remote) {
    const key = String(item?.privacy_key || '').trim()
    if (!key || textByKey.has(key)) continue
    textByKey.set(key, String(item?.privacy_text || '').trim())
    order.push(key)
  }
  if (!order.includes(ALBUM_WRITE_ONLY_PRIVACY_KEY)) {
    order.push(ALBUM_WRITE_ONLY_PRIVACY_KEY)
  }
  return order.map((key) => {
    const text = textByKey.get(key) || ''
    const isAlbum = key === ALBUM_WRITE_ONLY_PRIVACY_KEY
    return {
      privacy_key: key,
      label: PRIVACY_KEY_LABELS[key] || key,
      privacy_text: text || (isAlbum ? '尚未配置' : '—'),
      configured: Boolean(text),
      isAlbum,
    }
  })
}

/** @param {unknown} raw 微信 update_time，秒或毫秒时间戳 */
export function formatPrivacyUpdateTime(raw) {
  if (raw == null || raw === '') return ''
  const n = Number(raw)
  if (!Number.isFinite(n) || n <= 0) return String(raw)
  const ms = n < 1e12 ? n * 1000 : n
  const date = new Date(ms)
  if (Number.isNaN(date.getTime())) return String(raw)
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
