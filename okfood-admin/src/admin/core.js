import { ref, computed } from 'vue'

/**
 * 登录表单预填：仅本地 .env 可选配置，勿把真实密码提交到仓库。
 */
export const LOGIN_PRESET_USER = String(import.meta.env.VITE_ADMIN_LOGIN_PRESET_USER ?? '').trim()
export const LOGIN_PRESET_PASSWORD = String(
  import.meta.env.VITE_ADMIN_LOGIN_PRESET_PASSWORD ?? '',
).trim()
export const ADMIN_TOKEN_KEY = 'okfood_admin_access_token'
export const ADMIN_KIND_KEY = 'okfood_admin_kind'
const ENV_API_BASE = String(import.meta.env.VITE_API_BASE_URL || '').trim()
export const API_BASE = ENV_API_BASE.replace(/\/$/, '')

export const adminAccessToken = ref('')
export const rememberLogin = ref(false)
/** `full` | `delivery`，与登录 JWT / 接口 admin_kind 一致 */
export const adminKind = ref('full')
/** 会员列表：会员档案页写入，营业概览预览读取 */
export const memberList = ref([])

export const isLoggedIn = computed(() => Boolean(String(adminAccessToken.value || '').trim()))

/** @type {import('vue-router').Router | null} */
let adminRouter = null

/** @param {import('vue-router').Router} r */
export function registerAdminRouter(r) {
  adminRouter = r
}

function peekJwtRole(token) {
  const t = String(token || '').trim()
  if (!t) return null
  try {
    const seg = t.split('.')[1]
    if (!seg) return null
    const b64 = seg.replace(/-/g, '+').replace(/_/g, '/')
    const padLen = (4 - (b64.length % 4)) % 4
    const padded = b64 + '='.repeat(padLen)
    const json = JSON.parse(atob(padded))
    return typeof json.role === 'string' ? json.role : null
  } catch {
    return null
  }
}

function persistAdminKind(kind) {
  const k = kind === 'delivery' ? 'delivery' : 'full'
  adminKind.value = k
  try {
    if (rememberLogin.value) {
      localStorage.setItem(ADMIN_KIND_KEY, k)
      sessionStorage.removeItem(ADMIN_KIND_KEY)
    } else {
      sessionStorage.setItem(ADMIN_KIND_KEY, k)
      localStorage.removeItem(ADMIN_KIND_KEY)
    }
  } catch {
    /* ignore */
  }
}

/** 根据当前 token（及可选的登录响应）刷新 adminKind：JWT role 优先，解析失败时用登录接口 admin_kind。 */
function applyAdminKindFromCurrentToken(loginPayload = null) {
  const t = String(adminAccessToken.value || '').trim()
  if (!t) {
    adminKind.value = 'full'
    return
  }
  const role = peekJwtRole(t)
  let kind = 'full'
  if (role === 'admin_delivery') kind = 'delivery'
  else if (role === 'admin') kind = 'full'
  else {
    const raw = loginPayload && loginPayload.admin_kind
    if (raw === 'delivery' || raw === 'full') kind = raw === 'delivery' ? 'delivery' : 'full'
  }
  persistAdminKind(kind)
}

/** 登录成功后须先 setAdminToken，再调用本函数传入登录返回的 data。 */
export function syncAdminKindFromLoginPayload(data) {
  applyAdminKindFromCurrentToken(data && typeof data === 'object' ? data : null)
}

export function hydrateTokenFromStorage() {
  try {
    const fromLocal = localStorage.getItem(ADMIN_TOKEN_KEY)
    const fromSess = sessionStorage.getItem(ADMIN_TOKEN_KEY)
    adminAccessToken.value = (fromLocal || fromSess || '').trim()
    rememberLogin.value = Boolean(fromLocal)
    applyAdminKindFromCurrentToken()
  } catch {
    /* ignore */
  }
}

export function setAdminToken(token) {
  adminAccessToken.value = String(token || '').trim()
  try {
    if (rememberLogin.value) {
      localStorage.setItem(ADMIN_TOKEN_KEY, adminAccessToken.value)
      sessionStorage.removeItem(ADMIN_TOKEN_KEY)
    } else {
      sessionStorage.setItem(ADMIN_TOKEN_KEY, adminAccessToken.value)
      localStorage.removeItem(ADMIN_TOKEN_KEY)
    }
  } catch {
    /* ignore */
  }
  applyAdminKindFromCurrentToken()
}

export function clearAdminToken() {
  adminAccessToken.value = ''
  adminKind.value = 'full'
  try {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY)
    localStorage.removeItem(ADMIN_TOKEN_KEY)
    sessionStorage.removeItem(ADMIN_KIND_KEY)
    localStorage.removeItem(ADMIN_KIND_KEY)
  } catch {
    /* ignore */
  }
}

export function handleAdminLogout() {
  memberList.value = []
  clearAdminToken()
  adminRouter?.push({ name: 'login' })
}

/** 后端统一响应 { code, data, msg }；成功码见 isApiSuccessCode */
export function isApiEnvelope(x) {
  return (
    x &&
    typeof x === 'object' &&
    typeof x.code === 'number' &&
    'data' in x &&
    typeof x.msg === 'string'
  )
}

/** 0 与200 均视为成功（文档/网关常见0；本仓库后端为 200） */
export function isApiSuccessCode(code) {
  return code === 0 || code === 200
}

export function errorMessageFromBody(data, fallback) {
  if (data && isApiEnvelope(data) && typeof data.msg === 'string' && data.msg) {
    return data.msg
  }
  const d = data && data.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d
      .map((x) => {
        if (typeof x === 'string') return x
        if (x && typeof x.msg === 'string') return x.msg
        return JSON.stringify(x)
      })
      .join('；')
  }
  return fallback
}

export async function apiJson(path, init = {}, { auth = false } = {}) {
  const url = `${API_BASE}${path}`
  const headers = {
    'Content-Type': 'application/json',
    ...(init.headers || {}),
  }
  if (auth && adminAccessToken.value) {
    headers.Authorization = `Bearer ${adminAccessToken.value}`
  }
  const method = String(init.method || 'GET').toUpperCase()
  const res = await fetch(url, {
    cache: method === 'GET' ? 'no-store' : 'default',
    ...init,
    headers,
  })
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    /* 非 JSON */
  }
  if (!res.ok) {
    const msg = errorMessageFromBody(data, `请求失败 (${res.status})`)
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  if (isApiEnvelope(data)) {
    if (!isApiSuccessCode(data.code)) {
      const err = new Error(data.msg || '请求失败')
      err.status = res.status
      throw err
    }
    return data.data
  }
  return data
}

/** multipart 上传（不要设置 Content-Type，由浏览器带 boundary） */
export async function apiForm(path, formData, { auth = false } = {}) {
  const url = `${API_BASE}${path}`
  const headers = {}
  if (auth && adminAccessToken.value) {
    headers.Authorization = `Bearer ${adminAccessToken.value}`
  }
  const res = await fetch(url, { method: 'POST', body: formData, headers })
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    /* 非 JSON */
  }
  if (!res.ok) {
    const msg = errorMessageFromBody(data, `请求失败 (${res.status})`)
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  if (isApiEnvelope(data)) {
    if (!isApiSuccessCode(data.code)) {
      const err = new Error(data.msg || '请求失败')
      err.status = res.status
      throw err
    }
    return data.data
  }
  return data
}

/** 菜品图展示：相对路径 /static/... 需拼 API 根地址 */
export function dishImageDisplayUrl(u) {
  const s = (u || '').trim()
  if (!s) return ''
  if (/^https?:\/\//i.test(s) || s.startsWith('data:')) return s
  if (s.startsWith('/')) return `${API_BASE}${s}`
  return s
}

/** 已带管理员 Token 的 API 请求（供子组件使用） */
export function adminApiAuthenticated(path, init = {}) {
  return apiJson(path, init, { auth: true })
}

/** 月卡 / 周卡周期默认总次数；次卡为单次 +1（与充值选项一致） */
export function planDefaultTotal(planType) {
  if (planType === '月卡') return 24
  if (planType === '周卡') return 6
  if (planType === '次卡') return 1
  return null
}

/** API 日期字段规范为 YYYY-MM-DD */
function adminUserYmd(v) {
  if (v == null || v === '') return ''
  const s = String(v).trim()
  return s.length >= 10 ? s.slice(0, 10) : s
}

function ymdParts(ymd) {
  const s = adminUserYmd(ymd)
  if (s.length < 10) return null
  const y = Number(s.slice(0, 4))
  const m = Number(s.slice(5, 7))
  const d = Number(s.slice(8, 10))
  if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) return null
  return { y, m, d }
}

/** 单日请假文案：「M月d号」 */
function formatLeaveDaySingleLabel(ymd) {
  const p = ymdParts(ymd)
  return p ? `${p.m}月${p.d}号` : String(adminUserYmd(ymd) || '').trim()
}

/**
 * 跨日请假：同月年为「d号~d号」，否则补足月或年以防歧义
 */
function formatLeaveDayRangeLabel(rs, re) {
  const a = ymdParts(rs)
  const b = ymdParts(re)
  if (!a || !b) return `${adminUserYmd(rs)}~${adminUserYmd(re)}`

  if (a.y === b.y && a.m === b.m) {
    return `${a.d}号~${b.d}号`
  }
  if (a.y === b.y) {
    return `${a.m}月${a.d}号~${b.m}月${b.d}号`
  }
  return `${a.y}年${a.m}月${a.d}号~${b.y}年${b.m}月${b.d}号`
}

/** 列表「请假时间」：区间优先于「仅明日」 */
function buildLeaveListFields(raw) {
  const rs = adminUserYmd(raw.leave_range_start)
  const re = adminUserYmd(raw.leave_range_end)
  if (rs && re) {
    if (rs === re) {
      return {
        leave_kind: 'range_single',
        leave_badge: '',
        leave_detail: formatLeaveDaySingleLabel(rs),
      }
    }
    return {
      leave_kind: 'range_multi',
      leave_badge: '',
      leave_detail: formatLeaveDayRangeLabel(rs, re),
    }
  }
  if (raw.is_leaved_tomorrow === true) {
    const td = adminUserYmd(raw.tomorrow_leave_target_date)
    const label = td ? formatLeaveDaySingleLabel(td) : ''
    return {
      leave_kind: 'tomorrow',
      leave_badge: '',
      leave_detail: label || '目标日未绑定',
    }
  }
  return {
    leave_kind: '',
    leave_badge: '',
    leave_detail: '',
  }
}

/** GET /api/admin/users 单条映射为表格行 */
export function mapAdminUserToRow(raw, idx) {
  if (!raw || typeof raw !== 'object') {
    return {
      id: `row-${idx}`,
      name: '—',
      phone: '',
      balance: 0,
      delivery_start_date: '',
      balanceLabel: '0',
      totalQuota: null,
      area: '—',
      delivery_region_id: null,
      address: '',
      detail_address: '',
      plan: '次卡',
      remarks: '',
      daily_meal_units: 1,
      meal_quota_total: 0,
      wechat_name: '',
      is_active: false,
      delivery_deferred: false,
      is_on_leave_today: false,
      tomorrow_leave: false,
      leave_kind: '',
      leave_badge: '',
      leave_detail: '',
      status: '未开卡',
      store_pickup: false,
    }
  }
  const balance = Number(raw.balance) || 0
  const active = raw.is_active !== false
  const deferred = raw.delivery_deferred === true
  const onLeaveToday = raw.is_on_leave_today === true
  const tomorrowLeave = raw.is_leaved_tomorrow === true

  let status = '活跃中'
  if (!active) {
    if (deferred) status = '暂停配送'
    else status = '未开卡'
  }   else if (onLeaveToday) status = '请假中'
  else if (balance <= 2) status = '待续费'

  const plan = raw.plan_type || '次卡'
  const totalQuota = planDefaultTotal(plan)
  const mealQuotaTotal = Number(raw.meal_quota_total)
  const hasPersistedTotal = Number.isFinite(mealQuotaTotal) && mealQuotaTotal > 0
  // 有 meal_quota_total 时与 balance 组成「剩余/总」；否则沿用原周卡/月卡展示规则
  const displayTotal = hasPersistedTotal
    ? mealQuotaTotal
    : totalQuota != null
      ? Math.max(totalQuota, balance)
      : null
  const balanceLabel = displayTotal != null ? `${balance} / ${displayTotal}` : String(balance)

  const leaveList = buildLeaveListFields(raw)

  const ds = raw.delivery_start_date
  let deliveryStartYmd = ''
  if (ds != null && String(ds).trim()) {
    const s = String(ds).trim()
    deliveryStartYmd = s.length >= 10 ? s.slice(0, 10) : s
  }

  return {
    id: raw.id != null ? raw.id : raw.phone || `row-${idx}`,
    name: raw.name || '—',
    phone: raw.phone || '',
    balance,
    delivery_start_date: deliveryStartYmd,
    balanceLabel,
    totalQuota,
    area: raw.area || '—',
    delivery_region_id:
      raw.delivery_region_id != null && raw.delivery_region_id !== ''
        ? Number(raw.delivery_region_id)
        : null,
    address: raw.address || '',
    detail_address: typeof raw.detail_address === 'string' ? raw.detail_address : '',
    plan,
    remarks: raw.remarks ?? '',
    daily_meal_units: Math.max(1, Math.min(50, Number(raw.daily_meal_units) || 1)),
    meal_quota_total: hasPersistedTotal ? mealQuotaTotal : 0,
    wechat_name: raw.wechat_name ?? '',
    is_active: active,
    delivery_deferred: deferred,
    is_on_leave_today: onLeaveToday,
    tomorrow_leave: active && !onLeaveToday && tomorrowLeave,
    leave_kind: leaveList.leave_kind,
    leave_badge: leaveList.leave_badge,
    leave_detail: leaveList.leave_detail,
    status,
    store_pickup: raw.store_pickup === true,
  }
}
