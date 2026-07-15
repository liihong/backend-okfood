import { API_BASE } from '@/utils/api.js'

/** @typedef {{ weekStart: string, asOf: string, fetchedAt: number, items: unknown[] }} WeeklyMenuCacheEntry */

const STORAGE_KEY = 'okfood_weekly_menu_cache_v2'
const CACHE_SCHEMA_VERSION = 3
/** 超过该时长仍展示缓存，但会后台静默刷新 */
export const WEEKLY_MENU_STALE_MS = 30 * 60 * 1000
/** 超过该时长视为失效，必须重新拉取 */
export const WEEKLY_MENU_MAX_AGE_MS = 24 * 60 * 60 * 1000

function ymdTodayShanghai(now = new Date()) {
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
    /* ignore */
  }
  const d = new Date(now)
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${mo}-${day}`
}

function addDaysIso(isoDate, days) {
  if (!isoDate || typeof isoDate !== 'string') return ''
  const n = Math.floor(Number(days)) || 0
  const d = new Date(`${isoDate.trim()}T12:00:00+08:00`)
  if (Number.isNaN(d.getTime())) return ''
  d.setUTCDate(d.getUTCDate() + n)
  const y = d.getUTCFullYear()
  const m = String(d.getUTCMonth() + 1).padStart(2, '0')
  const day = String(d.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 上海时区：给定日期的当周周一 YYYY-MM-DD */
export function mondayOfWeekShanghai(now = new Date()) {
  const today = ymdTodayShanghai(now)
  const d = new Date(`${today}T12:00:00+08:00`)
  if (Number.isNaN(d.getTime())) return ''
  const dow = d.getUTCDay()
  const diff = dow === 0 ? -6 : 1 - dow
  return addDaysIso(today, diff)
}

/** @returns {{ v: number, apiBase: string, weeks: Record<string, WeeklyMenuCacheEntry> } | null} */
function readStore() {
  try {
    const raw = uni.getStorageSync(STORAGE_KEY)
    if (!raw || typeof raw !== 'object') return null
    if (raw.v !== CACHE_SCHEMA_VERSION || typeof raw.weeks !== 'object') return null
    return raw
  } catch {
    return null
  }
}

/** @param {{ v: number, apiBase: string, weeks: Record<string, WeeklyMenuCacheEntry> }} store */
function writeStore(store) {
  try {
    uni.setStorageSync(STORAGE_KEY, store)
  } catch {
    /* ignore quota */
  }
}

function emptyStore() {
  return { v: CACHE_SCHEMA_VERSION, apiBase: API_BASE, weeks: {} }
}

/**
 * @param {{ weekStart?: string, mealPeriod?: string }} [opts]
 * @returns {string} 缓存桶 key（当周周一 + 餐段）
 */
export function resolveWeeklyMenuCacheKey(opts = {}) {
  const ws =
    typeof opts.weekStart === 'string' && opts.weekStart.trim()
      ? opts.weekStart.trim()
      : mondayOfWeekShanghai()
  if (!ws) return ''
  const mp =
    typeof opts.mealPeriod === 'string' && opts.mealPeriod.trim()
      ? opts.mealPeriod.trim().toLowerCase()
      : 'lunch'
  return `${ws}:${mp}`
}

/**
 * @param {WeeklyMenuCacheEntry} entry
 * @param {string} cacheKey resolveWeeklyMenuCacheKey 返回值（weekStart:mealPeriod）
 */
function isEntryValid(entry, cacheKey) {
  if (!entry || typeof entry !== 'object') return false
  const expectedWeekStart = String(cacheKey || '').split(':')[0] || ''
  if (!expectedWeekStart || entry.weekStart !== expectedWeekStart) return false
  if (!Array.isArray(entry.items)) return false
  if (entry.asOf !== ymdTodayShanghai()) return false
  if (Date.now() - Number(entry.fetchedAt || 0) > WEEKLY_MENU_MAX_AGE_MS) return false
  return true
}

/**
 * @param {{ weekStart?: string }} [opts]
 * @returns {{ weekStart: string, items: unknown[], fetchedAt: number, stale: boolean } | null}
 */
export function peekWeeklyMenuCache(opts = {}) {
  const key = resolveWeeklyMenuCacheKey(opts)
  if (!key) return null
  const store = readStore()
  if (!store || store.apiBase !== API_BASE) return null
  const entry = store.weeks[key]
  if (!isEntryValid(entry, key)) return null
  const age = Date.now() - Number(entry.fetchedAt || 0)
  return {
    weekStart: entry.weekStart,
    items: entry.items,
    fetchedAt: entry.fetchedAt,
    stale: age > WEEKLY_MENU_STALE_MS,
  }
}

/** @param {{ weekStart: string, items: unknown[] }} payload @param {{ weekStart?: string, mealPeriod?: string }} [cacheOpts] */
export function writeWeeklyMenuCache(payload, cacheOpts = {}) {
  const weekStart =
    typeof payload.weekStart === 'string' ? payload.weekStart.trim() : ''
  if (!weekStart || !Array.isArray(payload.items)) return
  const key = resolveWeeklyMenuCacheKey({ weekStart, ...cacheOpts })
  if (!key) return
  let store = readStore()
  if (!store || store.apiBase !== API_BASE) store = emptyStore()
  store.weeks[key] = {
    weekStart,
    asOf: ymdTodayShanghai(),
    fetchedAt: Date.now(),
    items: payload.items,
  }
  writeStore(store)
}

/**
 * @param {string} [weekStart] 不传则清空全部周缓存
 */
export function invalidateWeeklyMenuCache(weekStart) {
  if (weekStart == null || weekStart === '') {
    try {
      uni.removeStorageSync(STORAGE_KEY)
    } catch {
      /* ignore */
    }
    return
  }
  const key = String(weekStart).trim()
  const store = readStore()
  if (!store || !store.weeks || !store.weeks[key]) return
  delete store.weeks[key]
  writeStore(store)
}
