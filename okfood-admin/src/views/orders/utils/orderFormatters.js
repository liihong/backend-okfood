import { parseApiDateTimeBeijing } from '../../../utils/beijingDateTime.js'

export function todayShanghaiStr() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const y = parts.find((p) => p.type === 'year')?.value || '1970'
  const mo = parts.find((p) => p.type === 'month')?.value || '01'
  const da = parts.find((p) => p.type === 'day')?.value || '01'
  return `${y}-${mo}-${da}`
}

/** ISO 日历日 YYYY-MM-DD → `2026年5月28日` */
export function formatIsoDateZh(isoDate) {
  if (isoDate == null || isoDate === '') return '—'
  const s = String(isoDate).trim().slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return s || '—'
  const y = Number(m[1])
  const mo = Number(m[2])
  const da = Number(m[3])
  if (!y || !mo || !da) return s
  return `${y}年${mo}月${da}日`
}

/** 展示用：将 Date 格式化为上海日历的 `MM-DD HH:mm` */
function formatShanghaiMdHm(d) {
  if (Number.isNaN(d.getTime())) return null
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(d)
  const mo = parts.find((p) => p.type === 'month')?.value ?? ''
  const da = parts.find((p) => p.type === 'day')?.value ?? ''
  const hr = parts.find((p) => p.type === 'hour')?.value ?? ''
  const mi = parts.find((p) => p.type === 'minute')?.value ?? ''
  if (!mo || !da) return null
  return `${mo}-${da} ${hr}:${mi}`
}

/** 下单时间：库内为北京时间 naive，统一解析后按上海展示为 `MM-DD HH:mm` */
export function formatOrderCreatedAtMdHm(iso) {
  if (iso == null || iso === '') return '—'
  const s = String(iso).trim()
  const shown = formatShanghaiMdHm(parseApiDateTimeBeijing(s))
  if (shown) return shown
  const x = s.replace('T', ' ')
  const m = x.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : x.slice(0, 16)
}

/** 下单时间拆分为「年月日 / 时分」，供列表分两行展示 */
export function orderCreatedAtParts(iso) {
  if (iso == null || iso === '') return { date: '—', time: '' }
  const s = String(iso).trim()
  const d = parseApiDateTimeBeijing(s)
  if (!Number.isNaN(d.getTime())) {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).formatToParts(d)
    const y = parts.find((p) => p.type === 'year')?.value ?? ''
    const mo = Number(parts.find((p) => p.type === 'month')?.value)
    const da = Number(parts.find((p) => p.type === 'day')?.value)
    const hr = parts.find((p) => p.type === 'hour')?.value ?? ''
    const mi = parts.find((p) => p.type === 'minute')?.value ?? ''
    const date = y && mo && da ? `${y}年${mo}月${da}日` : '—'
    const time = hr && mi ? `${hr}:${mi}` : ''
    return { date, time }
  }
  const dm = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (dm) {
    const tm = s.match(/(\d{2}):(\d{2})/)
    return {
      date: formatIsoDateZh(`${dm[1]}-${dm[2]}-${dm[3]}`),
      time: tm ? `${tm[1]}:${tm[2]}` : '',
    }
  }
  const full = formatOrderCreatedAtMdHm(iso)
  if (full === '—') return { date: '—', time: '' }
  const legacy = full.match(/^(\d{2}-\d{2})\s+(\d{2}:\d{2})$/)
  if (legacy) return { date: legacy[1], time: legacy[2] }
  return { date: full, time: '' }
}

/**
 * 列表「配送/自提」列：仅展示详细地址
 * @param {Record<string, unknown>} row
 */
export function singleOrderDeliveryAddressTextOnly(row) {
  if (!row || row.store_pickup) return '门店自提'
  const ra = String(row.routing_area ?? '').trim()
  const sum = String(row.address_summary ?? '').trim()
  if (!sum || sum === '—') return '—'
  if (ra && (sum === ra || sum.startsWith(`${ra} `))) {
    const rest = sum.slice(ra.length).trim()
    return rest || '—'
  }
  return sum
}

export function formatMemberAddressOption(a) {
  if (!a) return '—'
  const area = (a.area || '').trim()
  const full = (a.full_address || '').trim()
  const name = (a.contact_name || '').trim()
  const parts = [area, full].filter(Boolean)
  const line = parts.join(' ') || '—'
  return name ? `${name} · ${line}` : line
}
