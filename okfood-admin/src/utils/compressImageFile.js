import { MAX_UPLOAD_MB } from '../admin/core.js'

/** 与后端 settings.MAX_UPLOAD_BYTES 一致 */
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

const JPEG_QUALITY_STEPS = [0.88, 0.76, 0.64, 0.52]
const MAX_EDGE_STEPS = [1920, 1600, 1280, 1080]

/**
 * @param {Blob} blob
 * @returns {Promise<ImageBitmap | HTMLImageElement>}
 */
async function decodeImage(blob) {
  if (typeof createImageBitmap === 'function') {
    return createImageBitmap(blob)
  }
  const url = URL.createObjectURL(blob)
  try {
    const img = await new Promise((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error('图片读取失败'))
      el.src = url
    })
    return img
  } finally {
    URL.revokeObjectURL(url)
  }
}

/**
 * @param {HTMLCanvasElement} canvas
 * @param {number} quality
 * @returns {Promise<Blob>}
 */
function canvasToJpegBlob(canvas, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) reject(new Error('图片压缩失败'))
        else resolve(blob)
      },
      'image/jpeg',
      quality,
    )
  })
}

/**
 * @param {ImageBitmap | HTMLImageElement} image
 * @param {number} maxEdge
 */
function drawScaled(image, maxEdge) {
  const srcW = image.width || 0
  const srcH = image.height || 0
  if (srcW <= 0 || srcH <= 0) throw new Error('图片尺寸无效')
  const edge = Math.max(srcW, srcH)
  const scale = edge > maxEdge ? maxEdge / edge : 1
  const w = Math.max(1, Math.round(srcW * scale))
  const h = Math.max(1, Math.round(srcH * scale))
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('图片压缩失败')
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, w, h)
  ctx.drawImage(image, 0, 0, w, h)
  return canvas
}

function toJpegFile(blob, originalName) {
  const base = String(originalName || 'image').replace(/\.[^.]+$/, '')
  return new File([blob], `${base || 'image'}.jpg`, { type: 'image/jpeg' })
}

/**
 * 超过上传上限时自动压成 JPEG；GIF 无法有损压缩则直接提示。
 * @param {File} file
 * @returns {Promise<File>}
 */
export async function compressImageFileIfNeeded(file) {
  if (!(file instanceof Blob)) {
    throw new Error('请选择图片文件')
  }
  const type = String(file.type || '').toLowerCase()
  if (!type.startsWith('image/')) {
    throw new Error('请选择图片文件')
  }
  if (file.size <= MAX_UPLOAD_BYTES) return file
  if (type === 'image/gif') {
    throw new Error(`图片过大，请压缩后重试（单张不超过 ${MAX_UPLOAD_MB}MB）`)
  }

  const bitmap = await decodeImage(file)
  try {
    for (const maxEdge of MAX_EDGE_STEPS) {
      const canvas = drawScaled(bitmap, maxEdge)
      for (const quality of JPEG_QUALITY_STEPS) {
        const blob = await canvasToJpegBlob(canvas, quality)
        if (blob.size <= MAX_UPLOAD_BYTES) {
          return toJpegFile(blob, file.name)
        }
      }
    }
  } finally {
    if (typeof bitmap.close === 'function') bitmap.close()
  }
  throw new Error(`图片过大，请压缩后重试（单张不超过 ${MAX_UPLOAD_MB}MB）`)
}
