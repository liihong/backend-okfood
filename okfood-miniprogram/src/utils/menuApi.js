import { request } from '@/utils/api.js'
import {
  invalidateWeeklyMenuCache,
  mondayOfWeekShanghai,
  peekWeeklyMenuCache,
  resolveWeeklyMenuCacheKey,
  writeWeeklyMenuCache,
} from '@/utils/weeklyMenuCache.js'

export {
  invalidateWeeklyMenuCache,
  mondayOfWeekShanghai,
} from '@/utils/weeklyMenuCache.js'

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

/** 上海时区「明天」YYYY-MM-DD（最早可开始配送的业务日） */
export function ymdTomorrowShanghai(now = new Date()) {
  const today = ymdTodayShanghai(now)
  const anchor = new Date(`${today}T12:00:00+08:00`)
  anchor.setUTCDate(anchor.getUTCDate() + 1)
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(anchor)
    const y = parts.find((p) => p.type === 'year')?.value
    const m = parts.find((p) => p.type === 'month')?.value
    const d = parts.find((p) => p.type === 'day')?.value
    if (y && m && d) return `${y}-${m}-${d}`
  } catch {
    /* fallback */
  }
  const d2 = new Date(anchor)
  const yy = d2.getUTCFullYear()
  const mo = String(d2.getUTCMonth() + 1).padStart(2, '0')
  const day = String(d2.getUTCDate()).padStart(2, '0')
  return `${yy}-${mo}-${day}`
}

/** @param {string} isoDate YYYY-MM-DD */
export function dateToWeekdayLabel(isoDate) {
  if (!isoDate || typeof isoDate !== 'string') return ''
  const d = new Date(`${isoDate}T12:00:00`)
  if (Number.isNaN(d.getTime())) return ''
  const map = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return map[d.getDay()]
}

/** 供餐日展示：YYYY-MM-DD 周几 */
export function formatServiceDateYmdWithWeekday(ymd) {
  const t = String(ymd || '').trim()
  if (!t) return ''
  const w = dateToWeekdayLabel(t)
  return w ? `${t} ${w}` : t
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
  const spiceLabel =
    typeof item.spice_label === 'string' && item.spice_label.trim()
      ? item.spice_label.trim()
      : ''
  const singleStockLimited = item.single_stock_limited === true
  const singleStockRemainingRaw = item.single_stock_remaining
  const singleStockRemaining =
    singleStockRemainingRaw != null && singleStockRemainingRaw !== ''
      ? Math.max(0, Math.floor(Number(singleStockRemainingRaw)))
      : null
  /** 周菜单 include_stock=true 时接口会返回该字段，用于列表区分「未拉库存」与「售罄」 */
  const stockLoaded = Object.prototype.hasOwnProperty.call(item, 'single_stock_limited')
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
    spiceLabel,
    singleStockLimited,
    singleStockRemaining,
    stockLoaded,
  }
}

/** @param {unknown[] | null | undefined} items */
export function weeklyMenuItemsHaveStock(items) {
  if (!Array.isArray(items) || items.length === 0) return false
  return items.every((i) => i && typeof i === 'object' && i.stockLoaded === true)
}

/**
 * 写入周菜单缓存；若已有带库存条目，则不用无库存预取结果覆盖。
 * @param {{ weekStart: string, items: unknown[] }} payload
 * @param {{ weekStart?: string }} [cacheOpts]
 */
function writeWeeklyMenuCacheIfNotDowngrade(payload, cacheOpts = {}) {
  const weekStart = typeof payload.weekStart === 'string' ? payload.weekStart.trim() : ''
  if (!weekStart || !Array.isArray(payload.items)) return
  const existing = peekWeeklyMenuCache(
    weekStart ? { weekStart } : cacheOpts,
  )
  if (
    existing &&
    weeklyMenuItemsHaveStock(existing.items) &&
    !weeklyMenuItemsHaveStock(payload.items)
  ) {
    return
  }
  writeWeeklyMenuCache(payload)
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

export { minMemberDeliveryStartYmd } from '@/utils/memberDeliveryDate.js'

/**
 * 单点供餐日是否有效：上海「今天」及未来可下单，过去日期不可。
 * @param {string} [serviceDateYmd] YYYY-MM-DD
 * @param {{ now?: Date }} [opts]
 */
export function isSingleOrderServiceDate(serviceDateYmd, opts) {
  if (!serviceDateYmd || typeof serviceDateYmd !== 'string') return false
  const t = serviceDateYmd.trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return false
  const now = opts && opts.now != null ? opts.now : new Date()
  return t >= ymdTodayShanghai(now)
}

/**
 * 当日单点库存是否可售（未配置日总份视为不可售；已过供餐日一律不可售）。
 * @param {{ singleStockLimited?: boolean, singleStockRemaining?: number | null, serviceDate?: string } | null | undefined} menuItem
 * @param {string} [serviceDateYmd]
 * @param {{ now?: Date }} [opts]
 */
export function isSingleOrderStockAvailable(menuItem, serviceDateYmd, opts) {
  if (!menuItem || typeof menuItem !== 'object') return false
  const svc =
    (typeof serviceDateYmd === 'string' && serviceDateYmd.trim()) ||
    (typeof menuItem.serviceDate === 'string' && menuItem.serviceDate.trim()) ||
    ''
  if (svc && !isSingleOrderServiceDate(svc, opts)) return false
  if (!menuItem.singleStockLimited) return false
  const n = menuItem.singleStockRemaining
  return n != null && Number(n) > 0
}

/**
 * 是否可发起单点（供餐日 + 库存，列表/详情/确认页唯一入口）。
 * @param {{ dishId?: string, singleStockLimited?: boolean, singleStockRemaining?: number | null } | null | undefined} menuItem
 * @param {string} [serviceDateYmd]
 * @param {{ now?: Date }} [opts]
 */
export function canSubmitSingleOrder(menuItem, serviceDateYmd, opts) {
  if (!menuItem || typeof menuItem !== 'object') return false
  if ('dishId' in menuItem && !String(menuItem.dishId || '').trim()) return false
  if (!isSingleOrderServiceDate(serviceDateYmd, opts)) return false
  return isSingleOrderStockAvailable(menuItem)
}

/**
 * @param {{ singleStockLimited?: boolean, singleStockRemaining?: number | null } | null | undefined} menuItem
 * @param {string} [serviceDateYmd]
 * @param {{ now?: Date }} [opts]
 * @returns {string} 空串表示可下单
 */
export function singleOrderBlockReason(menuItem, serviceDateYmd, opts) {
  if (!isSingleOrderServiceDate(serviceDateYmd, opts)) {
    const t = String(serviceDateYmd || '').trim()
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return '供餐日期无效'
    return '不可选择过去的供餐日'
  }
  if (!menuItem) return ''
  if ('dishId' in menuItem && !String(menuItem.dishId || '').trim()) return '该餐品不可单点'
  if (!isSingleOrderStockAvailable(menuItem)) return '当日单次卡已无库存'
  return ''
}

/** @type {Map<string, Promise<{ weekStart: string, items: ReturnType<typeof mapWeeklyListItem>[] }>>} */
const weeklyMenuInflight = new Map()

/**
 * @param {Record<string, unknown>} data
 * @returns {{ weekStart: string, items: ReturnType<typeof mapWeeklyListItem>[] }}
 */
function normalizeWeeklyMenuResponse(data) {
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

/**
 * @param {{ weekStart?: string, includeStock?: boolean }} opts
 */
async function fetchWeeklyMenuFromNetwork(opts = {}) {
  const weekStart =
    typeof opts.weekStart === 'string' && opts.weekStart.trim()
      ? opts.weekStart.trim()
      : ''
  const includeStock = opts.includeStock === true
  const data = await request('/api/menu/weekly', {
    method: 'GET',
    data: {
      ...(weekStart ? { week_start: weekStart } : {}),
      include_stock: includeStock,
      ...(includeStock ? { as_of_date: ymdTodayShanghai() } : {}),
    },
    retry: 1,
  })
  return normalizeWeeklyMenuResponse(data)
}

/**
 * @param {{ weekStart?: string, includeStock?: boolean }} [opts]
 */
function weeklyInflightKey(opts = {}) {
  const base = resolveWeeklyMenuCacheKey(opts) || '__this__'
  return opts.includeStock === true ? `${base}:stock` : base
}

/**
 * 后台预取某周菜单（静默，失败忽略）。
 * @param {{ weekStart?: string }} [opts]
 */
export function prefetchWeeklyMenu(opts = {}) {
  const cached = peekWeeklyMenuCache(opts)
  if (cached && !cached.stale) return
  const key = weeklyInflightKey(opts)
  if (weeklyMenuInflight.has(key)) return
  const p = fetchWeeklyMenuFromNetwork({ ...opts, includeStock: false })
    .then((data) => {
      if (data.weekStart) writeWeeklyMenuCacheIfNotDowngrade(data, opts)
      return data
    })
    .catch(() => null)
    .finally(() => {
      weeklyMenuInflight.delete(key)
    })
  weeklyMenuInflight.set(key, p)
}

/**
 * @param {{ weekStart?: string, forceRefresh?: boolean, skipCache?: boolean, includeStock?: boolean }} [opts]
 *   - `forceRefresh` 忽略缓存直接请求
 *   - `skipCache` 不读不写缓存（调试用）
 *   - `includeStock` 列表展示剩余库存时传 true（仅当前可见周请求，预取仍不带库存）
 * @returns {Promise<{ weekStart: string, items: ReturnType<typeof mapWeeklyListItem>[] }>}
 */
export async function fetchWeeklyMenu(opts = {}) {
  const forceRefresh = opts.forceRefresh === true
  const skipCache = opts.skipCache === true
  const includeStock = opts.includeStock === true

  if (!forceRefresh && !skipCache) {
    const cached = peekWeeklyMenuCache(opts)
    if (cached && !cached.stale) {
      const cacheOk = !includeStock || weeklyMenuItemsHaveStock(cached.items)
      if (cacheOk) {
        return { weekStart: cached.weekStart, items: cached.items }
      }
    }
  }

  const networkOpts = { ...opts, includeStock }
  const key = weeklyInflightKey(networkOpts)
  let inflight = weeklyMenuInflight.get(key)
  if (!inflight) {
    inflight = fetchWeeklyMenuFromNetwork(networkOpts).finally(() => {
      weeklyMenuInflight.delete(key)
    })
    weeklyMenuInflight.set(key, inflight)
  }

  const data = await inflight
  if (!skipCache && data.weekStart) {
    writeWeeklyMenuCacheIfNotDowngrade(data, opts)
  }
  return data
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
    singleStockLimited: raw.single_stock_limited === true,
    singleStockRemaining:
      raw.single_stock_remaining != null && raw.single_stock_remaining !== ''
        ? Math.max(0, Math.floor(Number(raw.single_stock_remaining)))
        : null,
    spiceLabel:
      typeof raw.spice_label === 'string' && raw.spice_label.trim()
        ? raw.spice_label.trim()
        : '',
    /** 门店固定配送费（元）；自提展示价 = price - baseDeliveryFee */
    baseDeliveryFee:
      raw.base_delivery_fee_yuan ??
      raw.baseDeliveryFeeYuan ??
      raw.base_delivery_fee ??
      null,
  }
}

/**
 * @param {string} dishId
 * @param {string} [serviceDateYmd] 供餐日 YYYY-MM-DD，与详情/确认页用于剩余库存
 */
export async function fetchMenuDetail(dishId, serviceDateYmd) {
  const s = (serviceDateYmd && String(serviceDateYmd).trim()) || ''
  const q = s
    ? `?service_date=${encodeURIComponent(s)}`
    : ''
  const raw = await request(`/api/menu/detail/${encodeURIComponent(dishId)}${q}`, {
    method: 'GET',
    retry: 1,
  })
  return mapMenuDetail(raw)
}

/** @param {Record<string, unknown>} raw */
export function mapTodayMenuItem(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const mapped = mapWeeklyListItem(raw, 0)
  if (!mapped.dishId) return null
  return mapped
}

/**
 * 今日餐谱（上海业务日）。
 * @returns {Promise<ReturnType<typeof mapTodayMenuItem>>}
 */
export async function fetchTodayMenu() {
  const raw = await request('/api/menu/today', { method: 'GET', retry: 1 })
  return mapTodayMenuItem(raw)
}

/** @param {unknown} price */
export function formatMenuPrice(price) {
  if (price == null || price === '') return null
  const n = Number(price)
  if (!Number.isFinite(n)) return null
  return n
}
