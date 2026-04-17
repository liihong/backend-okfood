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

/**
 * 单次卡 / 单点：仅允许选「当日」「明日」供餐日下单（与周菜单 `serviceDate` 比较）
 * @param {string} [serviceDateYmd] YYYY-MM-DD
 */
export function isSingleOrderServiceDate(serviceDateYmd) {
  if (!serviceDateYmd || typeof serviceDateYmd !== 'string') return false
  const t = serviceDateYmd.trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return false
  const today = ymdTodayShanghai()
  const tomorrow = addDaysIso(today, 1)
  return t === today || t === tomorrow
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
