/**
 * 小程序 rich-text 内的 img 不受页面 CSS 约束，需写入内联样式才能按屏宽等比缩放。
 */

const IMG_FIT_STYLE = 'max-width:100%;height:auto;display:block;vertical-align:top;'

/**
 * 去掉 img 上会撑破屏幕的宽高，并强制按容器宽度等比缩放。
 * @param {string | null | undefined} html
 * @returns {string}
 */
export function fitRichTextHtml(html) {
  const raw = String(html || '')
  if (!raw) return ''
  return raw.replace(/<img\b([^>]*?)(\/?)>/gi, (_, attrs, slash) => {
    let next = String(attrs || '')
    next = next.replace(/\s+(width|height)\s*=\s*(['"][^'"]*['"]|[^\s>]+)/gi, '')
    if (/\bstyle\s*=/i.test(next)) {
      next = next.replace(/\bstyle\s*=\s*(['"])([\s\S]*?)\1/i, (_m, q, style) => {
        const cleaned = String(style)
          .replace(/(?:max-)?width\s*:\s*[^;]+;?/gi, '')
          .replace(/height\s*:\s*[^;]+;?/gi, '')
          .trim()
        const prefix = cleaned && !cleaned.endsWith(';') ? `${cleaned};` : cleaned
        return `style=${q}${prefix}${IMG_FIT_STYLE}${q}`
      })
    } else {
      next += ` style="${IMG_FIT_STYLE}"`
    }
    return `<img${next}${slash}>`
  })
}
