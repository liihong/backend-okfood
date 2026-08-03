/** Lodop 按后端 layout 打印（HTML 模式：微软雅黑 + 合理边距） */

import { loadLodop, mmToLodopUnit, listLocalPrinters } from './lodopLoader.js'

/** Lodop HTML 渲染字号系数（略小于 pt，避免撑版） */
const LODOP_HTML_FONT_FACTOR = 0.82

const PRINT_FONT = "'Microsoft YaHei','微软雅黑',Arial,'PingFang SC',sans-serif"

/** 顺丰面单底部条码区预留高度（mm，含条码+单号文字） */
const SF_WAYBILL_BARCODE_RESERVE_MM = 18
/** 顺丰条码相对页底上移量（mm，1cm） */
const SF_WAYBILL_BARCODE_LIFT_MM = 10

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function contentBottomMm(blocks) {
  let maxBottom = 0
  for (const b of blocks || []) {
    const y = Number(b.y_mm) || 0
    const h = Number(b.height_mm) || 5
    maxBottom = Math.max(maxBottom, y + h)
  }
  return maxBottom
}

function fitScale(blocks, paperH, marginBottom = 10) {
  const h = Number(paperH) || 150
  const bottom = contentBottomMm(blocks)
  const available = Math.max(50, h - marginBottom)
  if (bottom <= 0) return 1
  if (bottom <= available) return 1
  return Math.min(1, (available / bottom) * 0.92)
}

function ptToPx(pt) {
  return Math.max(9, Math.round(Number(pt) * (96 / 72) * LODOP_HTML_FONT_FACTOR))
}

function isDividerText(text) {
  const t = String(text || '').trim()
  return /^[-─—=.\s]+$/.test(t) && t.length >= 8
}

/** Lodop 坐标/尺寸：整数缺省为 px，必须显式带 mm 单位（与 SET_PRINT_PAGESIZE 的 0.1mm 整数不同）。 */
function mmStr(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '0mm'
  const rounded = Math.round(n * 10) / 10
  return `${rounded}mm`
}

function effectiveHeight(layout, fallback) {
  // 顺丰面单：始终用打印机配置的完整纸高（如 130mm），保证条码在同一页
  if (layout?.layout_style === 'sf_waybill') {
    return Number(layout.paper_height_mm) || fallback
  }
  const content = Number(layout.content_height_mm)
  if (Number.isFinite(content) && content > 0) return content
  return Number(layout.paper_height_mm) || fallback
}

/** SET_PRINT_PAGESIZE 在 intOrient=1 时 PageWidth/PageHeight 单位为 0.1mm */
function pagesizeUnit(mm) {
  return mmToLodopUnit(mm)
}

/** 顺丰面单：单表格流式排版；条码 LinkedItem 紧跟表格底部 */
function sfWaybillToTableHtml(layout) {
  const w = Number(layout.paper_width_mm) || 76
  const pad = Math.max(2, Number(layout.margin_left_mm) || 2)
  const store = escapeHtml(layout.header_text || 'OK饭')
  const mode = escapeHtml(layout.header_right_text || '配送')
  const body = layout.table_html || ''

  return (
    `<table style="width:${w}mm;border-collapse:collapse;border:none;">` +
    `<tr><td style="padding:${pad}mm ${pad}mm 2mm ${pad}mm;vertical-align:top;` +
    `font-family:${PRINT_FONT};color:#000;font-size:10px;line-height:1.35;">` +
    `<div style="display:flex;justify-content:space-between;align-items:center;` +
    `margin:0 0 1.5mm 0;font-size:11px;font-weight:700;line-height:1.3;">` +
    `<span>${store}</span><span>${mode}</span></div>` +
    body +
    `</td></tr></table>`
  )
}

function layoutToHtml(layout, paperW, paperH) {
  const w = Number(paperW) || 100
  const h = Number(paperH) || 150
  const fallbackMargin = Math.max(6, Number(layout.margin_left_mm) || 6)
  const blocks = layout.blocks || []
  const scale = fitScale(blocks, h)

  const htmlBlocks = blocks
    .map((b) => {
      const fs = Math.round(ptToPx(b.font_size_pt) * scale)
      const weight = b.bold ? '600' : 'normal'
      const align = b.align || 'left'
      const y = (Number(b.y_mm) || 0) * scale
      const bh = (Number(b.height_mm) || 5) * scale
      const x = Number(b.x_mm) >= 0 ? Number(b.x_mm) : fallbackMargin
      const bw = Number(b.width_mm) > 0 ? Number(b.width_mm) : w - x - fallbackMargin
      const isRemark = String(b.text || '').startsWith('【备注】')
      const isDivider = isDividerText(b.text)
      const isTipsLine = String(b.text || '').trim() === 'tips:' || /^tips:/.test(String(b.text || ''))
      const isLeftBody = align === 'left' && !isRemark
      let extra = `padding:0.4mm 1.5mm 0.4mm 2mm;height:${bh}mm;overflow:hidden;`
      if (isRemark) {
        extra += 'white-space:normal;word-break:break-all;line-height:1.25;background:#fef3c7;border:0.25mm solid #92400e;border-radius:0.5mm;'
      } else if (isDivider) {
        extra += 'color:#555;letter-spacing:0.2mm;line-height:1;white-space:nowrap;'
      } else if (isTipsLine) {
        extra += 'white-space:pre-line;line-height:1.2;'
      } else if (isLeftBody) {
        extra += 'white-space:normal;word-break:break-all;line-height:1.25;'
      } else {
        extra += 'white-space:nowrap;line-height:1.2;'
      }
      return `<div style="position:absolute;left:${x}mm;top:${y}mm;width:${bw}mm;font-size:${fs}px;font-weight:${weight};font-family:${PRINT_FONT};text-align:${align};${extra}">${escapeHtml(b.text)}</div>`
    })
    .join('')

  return `<table style="width:${w}mm;height:${h}mm;border-collapse:collapse;border:none;margin:0;padding:0;"><tr><td style="padding:0;margin:0;border:none;height:${h}mm;overflow:hidden;vertical-align:top;"><div style="position:relative;width:${w}mm;height:${h}mm;overflow:hidden;color:#000;">${htmlBlocks}</div></td></tr></table>`
}

function applyHtmItemStyle(lodop, layout) {
  if (layout?.layout_style === 'sf_waybill') return
  lodop.SET_PRINT_STYLEA(0, 'ItemType', 1)
}

function applyPrintOverflowMode(lodop, layout) {
  if (layout?.layout_style === 'sf_waybill') {
    lodop.SET_PRINT_MODE('FULL_HEIGHT_FOR_OVERFLOW', 0)
    lodop.SET_PRINT_MODE('FULL_WIDTH_FOR_OVERFLOW', 0)
    // 禁止因内容溢出自动追加空白页
    lodop.SET_PRINT_MODE('AUTO_CREATE_CUSTOM_PAGE', 0)
    return
  }
  lodop.SET_PRINT_MODE('FULL_HEIGHT_FOR_OVERFLOW', 1)
  lodop.SET_PRINT_MODE('FULL_WIDTH_FOR_OVERFLOW', 1)
}

function addSfWaybillBarcodes(lodop, layout, paperH, pad, barWidth) {
  const barcodes = layout.barcodes || []
  for (const bc of barcodes) {
    const code = String(bc.code || '').trim()
    if (!code) continue
    const heightMm = Number(bc.height_mm) || 14
    const bottomGap = 3
    const paperHmm = Number(paperH) || 130
    // 绝对 Y：纸高 - 条码高 - 底边距 - 上移量（BottomMargin 字符串在部分版本无效）
    const topMm = Math.max(0, paperHmm - heightMm - bottomGap - SF_WAYBILL_BARCODE_LIFT_MM)
    lodop.ADD_PRINT_BARCODE(
      mmStr(topMm),
      mmStr(pad),
      mmStr(barWidth),
      mmStr(heightMm),
      '128Auto',
      code,
    )
    lodop.SET_PRINT_STYLEA(0, 'ShowBarText', bc.show_text === false ? 0 : 1)
    if (bc.show_text !== false) {
      lodop.SET_PRINT_STYLEA(0, 'FontSize', 8)
      lodop.SET_PRINT_STYLEA(0, 'AlignJustify', 2)
    }
  }
}

function addLayoutContent(lodop, layout, paperW, paperH) {
  if (layout.layout_style === 'sf_waybill') {
    const html = sfWaybillToTableHtml(layout)
    const pad = Math.max(2, Number(layout.margin_left_mm) || 2)
    const barWidth = paperW - pad * 2
    const hasBarcode = (layout.barcodes || []).some((b) => String(b.code || '').trim())
    const tableHmm = hasBarcode
      ? Math.max(80, Number(paperH) - SF_WAYBILL_BARCODE_RESERVE_MM)
      : Number(paperH)
    // 表格限定在上部区域，下部留给顺丰条码
    lodop.ADD_PRINT_TABLE('0mm', '0mm', mmStr(paperW), mmStr(tableHmm), html)
    if (hasBarcode) {
      addSfWaybillBarcodes(lodop, layout, paperH, pad, barWidth)
    }
    return
  }
  const html = layoutToHtml(layout, paperW, paperH)
  lodop.ADD_PRINT_HTM('0mm', '0mm', mmStr(paperW), mmStr(paperH), html)
  applyHtmItemStyle(lodop, layout)
}

/**
 * @param {object} localPayload
 * @param {{ preview?: boolean, fallbackDefaultPrinter?: boolean }} [options]
 */
export async function printLocalPayload(localPayload, options = {}) {
  const preview = options.preview === true
  const lodop = await loadLodop()
  const defaultW = Number(localPayload.paper_width_mm) || 100
  const defaultH = Number(localPayload.paper_height_mm) || 150
  const hint = (localPayload.local_printer_name_hint || '').trim()
  const layouts = localPayload.layouts || []

  if (!layouts.length) {
    throw new Error('打印数据为空，请检查模板配置')
  }

  let printerMeta = { matched: !hint, fallback: false, name: '' }

  const first = layouts[0]
  const initW = Number(first.paper_width_mm || defaultW)
  const initH = effectiveHeight(first, defaultH)
  lodop.PRINT_INITA(0, 0, mmStr(initW), mmStr(initH), 'OK饭标签')

  printerMeta = await applyPrinterHint(lodop, hint, {
    fallbackDefaultPrinter: options.fallbackDefaultPrinter === true,
  })

  for (let i = 0; i < layouts.length; i += 1) {
    const layout = layouts[i]
    const lw = Number(layout.paper_width_mm || defaultW)
    const lh = effectiveHeight(layout, defaultH)
    if (i > 0) {
      lodop.NEWPAGEA()
    }
    // intOrient=1 固定纸高；勿用 intOrient=3 并把 lh 当 PageHeight（会被当成底边空白导致页面超长）
    lodop.SET_PRINT_PAGESIZE(1, pagesizeUnit(lw), pagesizeUnit(lh), '')
    applyPrintOverflowMode(lodop, layout)
    addLayoutContent(lodop, layout, lw, lh)
  }

  if (preview) {
    lodop.PREVIEW()
  } else {
    lodop.PRINT()
  }
  return printerMeta
}

async function applyPrinterHint(lodop, hint, options = {}) {
  if (!hint) return { matched: false, fallback: false, name: '' }
  const count = Number(lodop.GET_PRINTER_COUNT?.()) || 0
  for (let i = 0; i < count; i += 1) {
    const name = String(lodop.GET_PRINTER_NAME(i) || '')
    if (name === hint || name.includes(hint) || hint.includes(name)) {
      lodop.SET_PRINTER_INDEX(i)
      return { matched: true, fallback: false, name }
    }
  }
  if (options.fallbackDefaultPrinter) {
    const physical = pickPhysicalPrinter(lodop)
    if (physical) {
      lodop.SET_PRINTER_INDEX(physical.index)
      return { matched: false, fallback: true, name: physical.name, hint }
    }
  }
  const names = await listLocalPrinters()
  const sample = names.slice(0, 8).join('、') || '（无）'
  throw new Error(
    `未找到打印机「${hint}」。本机可用：${sample}${names.length > 8 ? '…' : ''}。请在「打印机管理」中将「本机 Windows 打印机名称」改为上述名称之一（与设备和打印机中完全一致）。`,
  )
}

function isVirtualPrinter(name) {
  const n = String(name || '').toLowerCase()
  return /pdf|xps|fax|onenote|microsoft print|send to|传真/.test(n)
}

function pickPhysicalPrinter(lodop) {
  const count = Number(lodop.GET_PRINTER_COUNT?.()) || 0
  for (let i = 0; i < count; i += 1) {
    const name = String(lodop.GET_PRINTER_NAME(i) || '')
    if (name && !isVirtualPrinter(name)) return { index: i, name }
  }
  return null
}
