/**
 * 会员端图片 URL：与后端 image_url_service 口径一致（OSS x-oss-process + 本地 _w480.webp 变体）。
 */

import { API_BASE } from '@/utils/api.js'

/** @typedef {'list' | 'banner' | 'logo' | 'detail' | 'poster'} ImagePresetName */

/** @type {Record<ImagePresetName, { w: number, q: number }>} */
export const IMAGE_PRESETS = {
  list: { w: 480, q: 82 },
  banner: { w: 750, q: 85 },
  logo: { w: 128, q: 85 },
  detail: { w: 1080, q: 88 },
  poster: { w: 750, q: 85 },
}

const VARIANT_SUFFIX_RE = /_w\d+\.webp$/i
const EXT_RE = /\.(jpe?g|png|gif|webp)$/i

/** @param {string} url */
function stripQuery(url) {
  return String(url || '').trim().split('?', 1)[0]
}

/** @param {string} url */
function isHttpUrl(url) {
  return /^https?:\/\//i.test(String(url || '').trim())
}

/** @param {string} url */
function preferOssProcess(url) {
  const u = String(url || '').trim()
  if (!isHttpUrl(u) || u.includes('x-oss-process=')) return false
  if (/\.aliyuncs\.com/i.test(u)) return true
  const assetBase = String(API_BASE || '').replace(/\/api\/?$/i, '')
  if (assetBase && u.startsWith(assetBase)) return true
  return false
}

/**
 * @param {string} originalUrl
 * @param {number} width
 */
export function variantSiblingUrl(originalUrl, width) {
  const raw = String(originalUrl || '').trim()
  if (!raw || VARIANT_SUFFIX_RE.test(stripQuery(raw))) return raw
  let pathOnly = raw
  if (isHttpUrl(raw)) {
    try {
      pathOnly = new URL(raw).pathname
    } catch {
      pathOnly = raw
    }
  }
  const siblingPath = EXT_RE.test(pathOnly)
    ? pathOnly.replace(EXT_RE, `_w${width}.webp`)
    : `${pathOnly}_w${width}.webp`
  if (isHttpUrl(raw)) {
    try {
      const u = new URL(raw)
      u.pathname = siblingPath
      u.search = ''
      u.hash = ''
      return u.toString()
    } catch {
      return raw
    }
  }
  return siblingPath
}

/**
 * @param {string} url
 * @param {{ w: number, q: number }} preset
 */
export function ossImageProcessUrl(url, preset) {
  const base = String(url || '').trim()
  if (!base || base.includes('x-oss-process=')) return base
  const w = Math.max(1, Math.floor(Number(preset?.w) || 480))
  const q = Math.max(1, Math.min(100, Math.floor(Number(preset?.q) || 82)))
  const process = `image/resize,w_${w}/quality,q_${q}/format,webp`
  const sep = base.includes('?') ? '&' : '?'
  return `${base}${sep}x-oss-process=${encodeURIComponent(process)}`
}

/**
 * @param {string | null | undefined} originalUrl
 * @param {string | null | undefined} [thumbUrl]
 * @param {ImagePresetName} [preset='list']
 */
export function optimizeImageUrl(originalUrl, thumbUrl, preset = 'list') {
  const thumb = typeof thumbUrl === 'string' ? thumbUrl.trim() : ''
  if (thumb) return thumb
  const orig = typeof originalUrl === 'string' ? originalUrl.trim() : ''
  if (!orig) return ''
  const p = IMAGE_PRESETS[preset] || IMAGE_PRESETS.list
  if (preferOssProcess(orig)) {
    return ossImageProcessUrl(orig, p)
  }
  const sibling = variantSiblingUrl(orig, p.w)
  return sibling || orig
}

/**
 * @param {string | null | undefined} originalUrl
 * @param {ImagePresetName} [preset='detail']
 */
export function optimizeDetailImageUrl(originalUrl, preset = 'detail') {
  return optimizeImageUrl(originalUrl, null, preset)
}
