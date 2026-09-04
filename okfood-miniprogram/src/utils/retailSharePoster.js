/**
 * 零售商品分享海报：太阳码 scene、Canvas 合成、保存相册。
 */

import { API_BASE } from '@/utils/api.js'
import { fetchRetailSharePoster } from '@/utils/catalogApi.js'

export const POSTER_WIDTH = 750
export const POSTER_HEIGHT = 1120

/**
 * @param {Record<string, unknown> | undefined} options
 * @returns {number}
 */
export function parseRetailSpuIdFromQuery(options) {
  const q = options && typeof options === 'object' ? options : {}
  const direct = Number(q.spu_id || q.id || 0)
  if (Number.isFinite(direct) && direct > 0) return Math.floor(direct)
  let scene = q.scene != null ? String(q.scene) : ''
  try {
    scene = decodeURIComponent(scene)
  } catch {
    /* 保持原值 */
  }
  const m =
    scene.match(/^r(\d+)$/i) ||
    scene.match(/(?:^|[?&])(?:spu_id|id)=(\d+)/i) ||
    scene.match(/^(\d+)$/)
  if (!m) return 0
  const n = Number(m[1])
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0
}

/** @returns {'release' | 'trial' | 'develop'} */
export function getMiniProgramEnvVersion() {
  try {
    if (typeof uni.getAccountInfoSync !== 'function') return 'release'
    const acc = uni.getAccountInfoSync()
    const v = acc && acc.miniProgram ? acc.miniProgram.envVersion : ''
    if (v === 'develop' || v === 'trial' || v === 'release') return v
  } catch {
    /* ignore */
  }
  return 'release'
}

/** @param {string | null | undefined} url */
function toAbsoluteUrl(url) {
  const u = String(url || '').trim()
  if (!u) return ''
  if (/^https?:\/\//i.test(u)) return u.split('#')[0]
  const origin = String(API_BASE || '').replace(/\/api\/?$/i, '').replace(/\/$/, '')
  if (!origin) return u
  return u.startsWith('/') ? `${origin}${u}` : `${origin}/${u}`
}

/** @param {string} url */
function downloadToLocal(url) {
  const abs = toAbsoluteUrl(url)
  if (!abs) return Promise.resolve('')
  return new Promise((resolve) => {
    uni.downloadFile({
      url: abs,
      success: (res) => {
        if (res.statusCode === 200 && res.tempFilePath) resolve(res.tempFilePath)
        else resolve('')
      },
      fail: () => resolve(''),
    })
  })
}

/** @param {string} b64 */
function writeWxacodeFile(b64) {
  const raw = String(b64 || '').replace(/^data:image\/\w+;base64,/, '')
  if (!raw) return Promise.reject(new Error('小程序码为空'))
  const fs = uni.getFileSystemManager()
  const root =
    (typeof wx !== 'undefined' && wx.env && wx.env.USER_DATA_PATH) ||
    (uni.env && uni.env.USER_DATA_PATH) ||
    ''
  if (!root) return Promise.reject(new Error('无法写入小程序码'))
  const filePath = `${root}/retail_wxacode_${Date.now()}.png`
  return new Promise((resolve, reject) => {
    fs.writeFile({
      filePath,
      data: raw,
      encoding: 'base64',
      success: () => resolve(filePath),
      fail: (e) => reject(e || new Error('写入小程序码失败')),
    })
  })
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} x
 * @param {number} y
 * @param {number} w
 * @param {number} h
 * @param {number} r
 */
function pathRoundRect(ctx, x, y, w, h, r) {
  const radius = Math.max(0, Math.min(r, w / 2, h / 2))
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.arcTo(x + w, y, x + w, y + h, radius)
  ctx.arcTo(x + w, y + h, x, y + h, radius)
  ctx.arcTo(x, y + h, x, y, radius)
  ctx.arcTo(x, y, x + w, y, radius)
  ctx.closePath()
}

/**
 * @param {HTMLCanvasElement} canvas
 * @param {string} src
 * @returns {Promise<WechatMiniprogram.Image | null>}
 */
function loadCanvasImage(canvas, src) {
  const path = String(src || '').trim()
  if (!path) return Promise.resolve(null)
  return new Promise((resolve) => {
    const img = canvas.createImage()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = path
  })
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {{ width: number, height: number }} img
 * @param {number} x
 * @param {number} y
 * @param {number} w
 * @param {number} h
 */
function drawImageCover(ctx, img, x, y, w, h) {
  const iw = Number(img.width) || 0
  const ih = Number(img.height) || 0
  if (!iw || !ih) return
  const scale = Math.max(w / iw, h / ih)
  const dw = iw * scale
  const dh = ih * scale
  const dx = x + (w - dw) / 2
  const dy = y + (h - dh) / 2
  ctx.drawImage(img, dx, dy, dw, dh)
}

/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} text
 * @param {number} maxWidth
 * @param {number} maxLines
 * @returns {string[]}
 */
function wrapLines(ctx, text, maxWidth, maxLines) {
  const src = String(text || '').trim()
  if (!src) return []
  const chars = [...src]
  /** @type {string[]} */
  const lines = []
  let line = ''
  for (let i = 0; i < chars.length; i += 1) {
    const test = line + chars[i]
    if (ctx.measureText(test).width <= maxWidth) {
      line = test
      continue
    }
    if (line) lines.push(line)
    line = chars[i]
    if (lines.length >= maxLines) {
      line = ''
      break
    }
  }
  if (line && lines.length < maxLines) lines.push(line)
  if (lines.length > maxLines) lines.length = maxLines
  const consumed = lines.join('').length
  if (lines.length === maxLines && consumed < src.length) {
    let last = lines[maxLines - 1] || ''
    while (last.length && ctx.measureText(`${last}…`).width > maxWidth) {
      last = last.slice(0, -1)
    }
    lines[maxLines - 1] = last ? `${last}…` : '…'
  }
  return lines
}

/**
 * @param {HTMLCanvasElement} canvas
 * @param {CanvasRenderingContext2D} ctx
 * @param {Record<string, unknown>} payload
 */
async function paintPoster(canvas, ctx, payload) {
  const W = POSTER_WIDTH
  const H = POSTER_HEIGHT
  const PAD = 36
  const avatarR = 28
  const imgX = PAD
  const imgY = 128
  const imgW = W - PAD * 2
  const imgH = 678
  const qrSize = 168
  const qrX = W - PAD - qrSize
  const footerY = imgY + imgH + 32
  const qrY = footerY
  const textMaxW = qrX - PAD - 24

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, W, H)
  ctx.textBaseline = 'top'

  const storeName = String(payload.store_name || 'OK饭').trim() || 'OK饭'
  const recommend = String(payload.recommend_text || '给你推荐了一个好东西').trim()
  const title = String(payload.title || '商品').trim() || '商品'
  const subtitle = String(payload.subtitle || '').trim()
  const priceRaw = payload.price_yuan
  const priceNum = Number(priceRaw)
  const priceText = Number.isFinite(priceNum) ? priceNum.toFixed(2) : String(priceRaw || '0.00')

  const [coverImg, logoImg, qrImg] = await Promise.all([
    loadCanvasImage(canvas, String(payload._coverLocal || '')),
    loadCanvasImage(canvas, String(payload._logoLocal || '')),
    loadCanvasImage(canvas, String(payload._qrLocal || '')),
  ])

  const ax = PAD + avatarR
  const ay = 32 + avatarR
  ctx.save()
  ctx.beginPath()
  ctx.arc(ax, ay, avatarR, 0, Math.PI * 2)
  ctx.closePath()
  ctx.clip()
  if (logoImg) {
    drawImageCover(ctx, logoImg, ax - avatarR, ay - avatarR, avatarR * 2, avatarR * 2)
  } else {
    ctx.fillStyle = '#0d5c46'
    ctx.fillRect(ax - avatarR, ay - avatarR, avatarR * 2, avatarR * 2)
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 28px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText([...storeName][0] || '店', ax, ay)
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
  }
  ctx.restore()

  ctx.fillStyle = '#111111'
  ctx.font = 'bold 30px sans-serif'
  ctx.fillText(storeName, PAD + avatarR * 2 + 16, 34)
  ctx.fillStyle = '#999999'
  ctx.font = '22px sans-serif'
  ctx.fillText(recommend, PAD + avatarR * 2 + 16, 76)

  ctx.save()
  pathRoundRect(ctx, imgX, imgY, imgW, imgH, 20)
  ctx.clip()
  if (coverImg) {
    drawImageCover(ctx, coverImg, imgX, imgY, imgW, imgH)
  } else {
    ctx.fillStyle = '#f1f5f9'
    ctx.fillRect(imgX, imgY, imgW, imgH)
    ctx.fillStyle = '#94a3b8'
    ctx.font = '28px sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('暂无图片', imgX + imgW / 2, imgY + imgH / 2)
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
  }
  ctx.restore()

  ctx.fillStyle = '#c2410c'
  ctx.font = '28px sans-serif'
  ctx.fillText('¥', PAD, footerY + 4)
  ctx.font = 'bold 44px sans-serif'
  ctx.fillText(priceText, PAD + 36, footerY)

  ctx.fillStyle = '#111111'
  ctx.font = 'bold 28px sans-serif'
  const titleLines = wrapLines(ctx, title, textMaxW, 2)
  let ty = footerY + 60
  titleLines.forEach((ln) => {
    ctx.fillText(ln, PAD, ty)
    ty += 38
  })
  if (subtitle) {
    ctx.fillStyle = '#888888'
    ctx.font = '22px sans-serif'
    const subLines = wrapLines(ctx, subtitle, textMaxW, 2)
    subLines.forEach((ln) => {
      ctx.fillText(ln, PAD, ty)
      ty += 30
    })
  }

  if (qrImg) {
    ctx.drawImage(qrImg, qrX, qrY, qrSize, qrSize)
    if (logoImg) {
      const hole = 52
      const hx = qrX + (qrSize - hole) / 2
      const hy = qrY + (qrSize - hole) / 2
      ctx.save()
      ctx.beginPath()
      ctx.arc(hx + hole / 2, hy + hole / 2, hole / 2, 0, Math.PI * 2)
      ctx.closePath()
      ctx.fillStyle = '#ffffff'
      ctx.fill()
      ctx.clip()
      drawImageCover(ctx, logoImg, hx, hy, hole, hole)
      ctx.restore()
    }
  }
}

/**
 * @param {HTMLCanvasElement} canvas
 * @param {Record<string, unknown>} payload
 * @returns {Promise<string>}
 */
export async function renderRetailSharePoster(canvas, payload) {
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('画布不可用')
  canvas.width = POSTER_WIDTH
  canvas.height = POSTER_HEIGHT
  await paintPoster(canvas, ctx, payload)
  return new Promise((resolve, reject) => {
    uni.canvasToTempFilePath({
      canvas,
      x: 0,
      y: 0,
      width: POSTER_WIDTH,
      height: POSTER_HEIGHT,
      destWidth: POSTER_WIDTH,
      destHeight: POSTER_HEIGHT,
      fileType: 'jpg',
      quality: 0.92,
      success: (res) => {
        if (res.tempFilePath) resolve(res.tempFilePath)
        else reject(new Error('海报导出失败'))
      },
      fail: (e) => reject(e || new Error('海报导出失败')),
    })
  })
}

/**
 * @param {number} spuId
 * @param {{ priceYuan?: string | number | null, coverUrl?: string | null }} [overrides]
 */
export async function loadRetailSharePosterAssets(spuId, overrides = {}) {
  const env = getMiniProgramEnvVersion()
  const data = await fetchRetailSharePoster(spuId, env)
  const cover = String(overrides.coverUrl || data.cover_image_url || '').trim()
  const logo = String(data.store_logo_url || '').trim()
  const [coverLocal, logoLocal, qrLocal] = await Promise.all([
    downloadToLocal(cover).then((p) => p || toAbsoluteUrl(cover)),
    downloadToLocal(logo).then((p) => p || toAbsoluteUrl(logo)),
    writeWxacodeFile(String(data.wxacode_base64 || '')),
  ])
  const price = overrides.priceYuan != null && String(overrides.priceYuan).trim() !== ''
    ? overrides.priceYuan
    : data.price_yuan
  return {
    ...data,
    price_yuan: price,
    cover_image_url: cover || data.cover_image_url,
    _coverLocal: coverLocal,
    _logoLocal: logoLocal,
    _qrLocal: qrLocal,
  }
}

/** @param {string} filePath */
export function savePosterToAlbum(filePath) {
  const path = String(filePath || '').trim()
  if (!path) return Promise.reject(new Error('海报文件不存在'))
  return new Promise((resolve, reject) => {
    uni.saveImageToPhotosAlbum({
      filePath: path,
      success: () => resolve(),
      fail: (err) => reject(err || new Error('保存失败')),
    })
  })
}
