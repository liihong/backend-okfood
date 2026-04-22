import { request } from '@/utils/api.js'

const PLACEHOLDER_IMG =
  'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400'

/** 上海时区当日 YYYY-MM-DD（与配送业务日一致） */
export function ymdTodayShanghai(now = new Date()) {
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(now)
    const y = parts.find((p) => p.type === 'year')?.value
    const m = parts.find((p) => p.type === 'month')?.value
    const d = parts.find((p) => p.type === 'day')?.value
    if (y && m && d) return `${y}-${m}-${d}`
  } catch {
    /* 部分基础库 Intl 异常时退回本地日历 */
  }
  const d = new Date(now)
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${mo}-${day}`
}

/** @param {string} isoDate YYYY-MM-DD */
export function dateToWeekdayLabel(isoDate) {
  if (!isoDate || typeof isoDate !== 'string') return ''
  const d = new Date(`${isoDate}T12:00:00`)
  if (Number.isNaN(d.getTime())) return ''
  const map = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return map[d.getDay()]
}

/** @param {Record<string, unknown> | null | undefined} item */
function weeklyRowDishIdRaw(item) {
  if (!item || typeof item !== 'object') return null
  return (
    item.dish_id ??
    item.dishId ??
    item.food_id ??
    item.foodId ??
    item.order_id ??
    item.orderId ??
    item.id
  )
}

/**
 * @param {Record<string, unknown>} item
 * @param {number} index
 */
function mapWeeklyListItem(item, index) {
  const date = item.date != null ? String(item.date) : ''
  const slot = item.slot
  const idRaw = weeklyRowDishIdRaw(item)
  const dishId = idRaw != null && idRaw !== '' ? String(idRaw) : ''
  const pic = item.pic ?? item.image_url ?? item.img
  const rowKey =
    dishId || (date ? `${date}-${slot != null ? slot : index}` : `week-${index}`)
  return {
    dishId,
    serviceDate: date,
    rowKey,
    day:
      (typeof item.weekday === 'string' && item.weekday) ||
      (typeof item.week_day === 'string' && item.week_day) ||
      dateToWeekdayLabel(date),
    name:
      (typeof item.title === 'string' && item.title) ||
      (typeof item.dish_name === 'string' && item.dish_name) ||
      (typeof item.name === 'string' && item.name) ||
      (dishId ? '餐品' : ''),
    ingredients:
      (typeof item.desc === 'string' && item.desc) ||
      (typeof item.description === 'string' && item.description) ||
      (dishId ? '暂未公布' : ''),
    price:
      item.price ??
      item.single_order_price_yuan ??
      item.singleOrderPriceYuan,
    img:
      (typeof pic === 'string' && pic) || (dishId ? PLACEHOLDER_IMG : ''),
  }
}

/**
 * @param {string} isoDate YYYY-MM-DD
 * @param {number} days
 * @returns {string}
 */
export function addDaysIso(isoDate, days) {
  if (!isoDate || typeof isoDate !== 'string') return ''
  const n = Math.floor(Number(days)) || 0
  const d = new Date(`${isoDate.trim()}T12:00:00`)
  if (Number.isNaN(d.getTime())) return ''
  d.setDate(d.getDate() + n)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 单点：上海时间该时刻起不可再下「当日供餐」单（与后端 `time(10,0,0)` 一致，含 10:00:00 起算） */
export const SINGLE_ORDER_CUTOFF_HOUR = 10

/**
 * 上海时区是否已过单点业务「当日」截单点（与后端 `time(10,0,0)` 一致）
 * @param {Date} [now]
 * @param {number} [cutoffHour] 默认 10
 */
export function isShanghaiPastDailyCutoff(
  now = new Date(),
  cutoffHour = SINGLE_ORDER_CUTOFF_HOUR,
) {
  const h0 = Math.floor(Number(cutoffHour)) || 0
  try {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Shanghai',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).formatToParts(now)
    const h = parseInt(parts.find((p) => p.type === 'hour')?.value || '0', 10) || 0
    const min = parseInt(parts.find((p) => p.type === 'minute')?.value || '0', 10) || 0
    const sec = parseInt(parts.find((p) => p.type === 'second')?.value || '0', 10) || 0
    if (h > h0) return true
    if (h < h0) return false
    return min > 0 || sec > 0
  } catch {
    const d = new Date(now)
    return d.getHours() > h0 || (d.getHours() === h0 && (d.getMinutes() > 0 || d.getSeconds() > 0))
  }
}

/**
 * 单点：仅「当日」「明日」供餐日可下单；全体会员在当日 10:00（上海）后不可再下「当日」单，仅可次日
 * @param {string} [serviceDateYmd] YYYY-MM-DD
 * @param {{ now?: Date }} [opts] 可传 `now` 便于测试
 */
export function isSingleOrderServiceDate(serviceDateYmd, opts) {
  if (!serviceDateYmd || typeof serviceDateYmd !== 'string') return false
  const t = serviceDateYmd.trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return false
  const now = opts && opts.now != null ? opts.now : new Date()
  const today = ymdTodayShanghai(now)
  const tomorrow = addDaysIso(today, 1)
  if (t !== today && t !== tomorrow) return false
  if (!isShanghaiPastDailyCutoff(now)) return true
  return t === tomorrow
}

/**
 * @param {string} serviceDateYmd
 * @param {{ now?: Date }} [opts]
 * @returns {string} 空串表示可下单
 */
export function singleOrderServiceDateError(serviceDateYmd, opts) {
  if (isSingleOrderServiceDate(serviceDateYmd, opts)) return ''
  const now = opts && opts.now != null ? opts.now : new Date()
  const t = String(serviceDateYmd || '').trim()
  const today = ymdTodayShanghai(now)
  const inWindow = t === today || t === addDaysIso(today, 1)
  if (inWindow && isShanghaiPastDailyCutoff(now) && t === today) {
    return '每日 10:00 后仅可下次日及之后的单点单'
  }
  return '仅当日与次日餐品可单点'
}

/**
 * @param {{ weekStart?: string }} [opts] 传 `week_start` 为当周任意一天（后端归一为周一）；不传为服务端「本周」
 * @returns {Promise<{ weekStart: string, items: ReturnType<typeof mapWeeklyListItem>[] }>}
 */
export async function fetchWeeklyMenu(opts = {}) {
  const weekStart =
    typeof opts.weekStart === 'string' && opts.weekStart.trim()
      ? opts.weekStart.trim()
      : ''
  const data = await request('/api/menu/weekly', {
    method: 'GET',
    data: weekStart ? { week_start: weekStart } : {},
    retry: 1,
  })
  const items = Array.isArray(data?.items) ? data.items : []
  const withDish = items.filter((row) => {
    const id = weeklyRowDishIdRaw(row)
    return id != null && id !== ''
  })
  return {
    weekStart: data?.week_start != null ? String(data.week_start) : '',
    items: withDish.map((row, i) => mapWeeklyListItem(row, i)),
  }
}

/** @param {Record<string, unknown>} raw */
export function mapMenuDetail(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const date = raw.date != null ? String(raw.date) : ''
  const pic = raw.pic ?? raw.image_url ?? raw.img
  return {
    dishId:
      raw.dish_id != null
        ? String(raw.dish_id)
        : raw.dishId != null
          ? String(raw.dishId)
          : raw.food_id != null
            ? String(raw.food_id)
            : raw.foodId != null
              ? String(raw.foodId)
              : raw.order_id != null
                ? String(raw.order_id)
                : raw.orderId != null
                  ? String(raw.orderId)
                  : '',
    day:
      (typeof raw.weekday === 'string' && raw.weekday) ||
      (typeof raw.week_day === 'string' && raw.week_day) ||
      dateToWeekdayLabel(date),
    name:
      (typeof raw.dish_name === 'string' && raw.dish_name) ||
      (typeof raw.title === 'string' && raw.title) ||
      (typeof raw.name === 'string' && raw.name) ||
      '餐品',
    ingredients:
      (typeof raw.description === 'string' && raw.description) ||
      (typeof raw.desc === 'string' && raw.desc) ||
      '',
    price:
      raw.price ??
      raw.single_order_price_yuan ??
      raw.singleOrderPriceYuan,
    img: (typeof pic === 'string' && pic) || PLACEHOLDER_IMG,
  }
}

/** @param {string} dishId */
export async function fetchMenuDetail(dishId) {
  const raw = await request(`/api/menu/detail/${encodeURIComponent(dishId)}`, {
    method: 'GET',
    retry: 1,
  })
  return mapMenuDetail(raw)
}

/** @param {unknown} price */
export function formatMenuPrice(price) {
  if (price == null || price === '') return null
  const n = Number(price)
  if (!Number.isFinite(n)) return null
  return n
}
