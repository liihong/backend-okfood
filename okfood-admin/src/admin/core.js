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
/** 管理端当前操作门店（多店时须与后端 store_id 一致） */
export const ADMIN_STORE_ID_KEY = 'okfood_admin_store_id'
const ENV_API_BASE = String(import.meta.env.VITE_API_BASE_URL || '').trim()
export const API_BASE = ENV_API_BASE.replace(/\/$/, '')

export const adminAccessToken = ref('')
export const rememberLogin = ref(false)
/** 管理端当前门店 id，默认 1；可通过 VITE_ADMIN_DEFAULT_STORE_ID 覆盖 */
const ENV_DEFAULT_STORE_ID = Number(import.meta.env.VITE_ADMIN_DEFAULT_STORE_ID) || 1
export const adminStoreId = ref(ENV_DEFAULT_STORE_ID)
/** `full` | `delivery` | `support` | `system`，与登录 JWT / 接口 admin_kind 一致 */
export const adminKind = ref('full')
/** 租户订阅状态（店主/配送/客服续费提醒） */
export const adminTenantSubscription = ref(null)
/** 会员列表：会员档案页写入，营业概览预览读取 */
export const memberList = ref([])

export const isLoggedIn = computed(() => Boolean(String(adminAccessToken.value || '').trim()))

/** @type {import('vue-router').Router | null} */
let adminRouter = null

/** @param {import('vue-router').Router} r */
export function registerAdminRouter(r) {
  adminRouter = r
}

/**
 * 解析管理端 JWT payload（仅客户端展示用，勿用于安全决策）。
 * @param {string | undefined | null} token
 * @returns {object | null} 含 role、sub；失败为 null
 */
function peekJwtPayload(token) {
  const t = String(token || '').trim()
  if (!t) return null
  try {
    const seg = t.split('.')[1]
    if (!seg) return null
    const b64 = seg.replace(/-/g, '+').replace(/_/g, '/')
    const padLen = (4 - (b64.length % 4)) % 4
    const padded = b64 + '='.repeat(padLen)
    const json = JSON.parse(atob(padded))
    const role = typeof json.role === 'string' ? json.role : null
    const subRaw = typeof json.sub === 'string' ? json.sub.trim() : ''
    return { role, sub: subRaw }
  } catch {
    return null
  }
}

/** @param {string | undefined | null} token */
function peekJwtRole(token) {
  const p = peekJwtPayload(token)
  return p && p.role != null ? p.role : null
}

/**
 * 管理端 JWT 的 subject（与后端 issue_admin_token 的 username 一致），用于顶栏展示登录名。
 * @param {string | undefined | null} token
 * @returns {string}
 */
export function peekAdminJwtUsername(token) {
  const p = peekJwtPayload(token)
  const s = (p && p.sub ? String(p.sub) : '').trim()
  return s
}

function persistAdminKind(kind) {
  const k =
    kind === 'delivery'
      ? 'delivery'
      : kind === 'support'
        ? 'support'
        : kind === 'system'
          ? 'system'
          : 'full'
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
  else if (role === 'admin_support') kind = 'support'
  else if (role === 'admin_system') kind = 'system'
  else if (role === 'admin') kind = 'full'
  else {
    const raw = loginPayload && loginPayload.admin_kind
    if (raw === 'delivery' || raw === 'support' || raw === 'system' || raw === 'full')
      kind =
        raw === 'delivery'
          ? 'delivery'
          : raw === 'support'
            ? 'support'
            : raw === 'system'
              ? 'system'
              : 'full'
  }
  persistAdminKind(kind)
}

/** 登录成功后须先 setAdminToken，再调用本函数传入登录返回的 data。 */
export function syncAdminKindFromLoginPayload(data) {
  applyAdminKindFromCurrentToken(data && typeof data === 'object' ? data : null)
  syncAdminTenantSubscriptionFromPayload(data)
}

/** 从登录或订阅接口同步租户续费状态 */
export function syncAdminTenantSubscriptionFromPayload(data) {
  const raw = data && typeof data === 'object' ? data.tenant_subscription : null
  if (!raw || typeof raw !== 'object') {
    adminTenantSubscription.value = null
    return
  }
  adminTenantSubscription.value = {
    expires_at: raw.expires_at != null ? String(raw.expires_at) : null,
    days_until_expiry:
      raw.days_until_expiry == null || Number.isNaN(Number(raw.days_until_expiry))
        ? null
        : Number(raw.days_until_expiry),
    status: typeof raw.status === 'string' ? raw.status : 'unset',
    remind_days: Number(raw.remind_days) > 0 ? Number(raw.remind_days) : 30,
  }
}

/** 拉取当前租户订阅状态（续费提醒横幅） */
export async function fetchAdminTenantSubscription() {
  if (!String(adminAccessToken.value || '').trim()) {
    adminTenantSubscription.value = null
    return null
  }
  if (adminKind.value === 'system') {
    adminTenantSubscription.value = null
    return null
  }
  try {
    const data = await apiJson('/api/admin/tenant-subscription', {}, { auth: true })
    syncAdminTenantSubscriptionFromPayload({ tenant_subscription: data })
    return adminTenantSubscription.value
  } catch {
    return adminTenantSubscription.value
  }
}

export function hydrateTokenFromStorage() {
  try {
    const fromLocal = localStorage.getItem(ADMIN_TOKEN_KEY)
    const fromSess = sessionStorage.getItem(ADMIN_TOKEN_KEY)
    adminAccessToken.value = (fromLocal || fromSess || '').trim()
    rememberLogin.value = Boolean(fromLocal)
    applyAdminKindFromCurrentToken()
    hydrateAdminStoreFromStorage()
  } catch {
    /* ignore */
  }
}

/** 从本地存储恢复管理端门店 id */
export function hydrateAdminStoreFromStorage() {
  try {
    const raw =
      localStorage.getItem(ADMIN_STORE_ID_KEY) ||
      sessionStorage.getItem(ADMIN_STORE_ID_KEY)
    const n = Number(raw)
    if (Number.isFinite(n) && n >= 1) adminStoreId.value = Math.floor(n)
  } catch {
    /* ignore */
  }
}

/** 切换管理端操作门店（写入与 token 相同的持久化策略） */
export function setAdminStoreId(storeId) {
  const sid = Math.max(1, Math.floor(Number(storeId) || ENV_DEFAULT_STORE_ID))
  adminStoreId.value = sid
  try {
    if (rememberLogin.value) {
      localStorage.setItem(ADMIN_STORE_ID_KEY, String(sid))
      sessionStorage.removeItem(ADMIN_STORE_ID_KEY)
    } else {
      sessionStorage.setItem(ADMIN_STORE_ID_KEY, String(sid))
      localStorage.removeItem(ADMIN_STORE_ID_KEY)
    }
  } catch {
    /* ignore */
  }
}

/** 管理端 API：未显式带 store_id 时自动追加当前门店 */
function appendAdminStoreIdQuery(path) {
  const p = String(path || '')
  if (!p.startsWith('/api/admin')) return p
  if (/[?&]store_id=/.test(p)) return p
  const sid = Math.max(1, Math.floor(Number(adminStoreId.value) || ENV_DEFAULT_STORE_ID))
  const sep = p.includes('?') ? '&' : '?'
  return `${p}${sep}store_id=${sid}`
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
  adminTenantSubscription.value = null
  try {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY)
    localStorage.removeItem(ADMIN_TOKEN_KEY)
    sessionStorage.removeItem(ADMIN_KIND_KEY)
    localStorage.removeItem(ADMIN_KIND_KEY)
  } catch {
    /* ignore */
  }
}

/**
 * 401 时清空登录并跳转登录页。
 * @param {unknown} [err] 传入 apiJson 抛出的 Error（含 status）时，仅 status===401 才登出并返回 true。
 * @returns {boolean} 是否已处理为登出
 */
export function handleAdminLogout(err) {
  if (err != null) {
    const status =
      err && typeof err === 'object' && 'status' in err ? Number(err.status) : 0
    if (status !== 401) return false
  }
  memberList.value = []
  clearAdminToken()
  adminRouter?.push({ name: 'login' })
  return true
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
  const reqPath = auth ? appendAdminStoreIdQuery(path) : path
  const url = `${API_BASE}${reqPath}`
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

/**
 * 二进制响应（如 xlsx）：成功返回 Blob。失败时抛出带 status 的 Error（与 apiJson 一致；401 由调用方 handleAdminLogout）。
 * @returns {Promise<{ blob: Blob, status: number }>}
 */
export async function apiBlob(path, init = {}, { auth = false } = {}) {
  const reqPath = auth ? appendAdminStoreIdQuery(path) : path
  const url = `${API_BASE}${reqPath}`
  const headers = {
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
  const blob = await res.blob()
  if (!res.ok) {
    const status = res.status
    let text = ''
    try {
      text = await blob.text()
    } catch {
      text = ''
    }
    let data = null
    try {
      data = text ? JSON.parse(text) : null
    } catch {
      /* ignore */
    }
    const msg = errorMessageFromBody(data, `请求失败 (${status})`)
    const err = new Error(msg)
    err.status = status
    throw err
  }
  return { blob, status: res.status }
}

/** multipart 上传（不要设置 Content-Type，由浏览器带 boundary） */
export async function apiForm(path, formData, { auth = false } = {}) {
  const reqPath = auth ? appendAdminStoreIdQuery(path) : path
  const url = `${API_BASE}${reqPath}`
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

/** 餐段资格 → 午餐 / 晚餐 / 全餐 */
export function mealScopeLabelFromPeriods(periods) {
  const set = new Set(Array.isArray(periods) ? periods.map((x) => String(x || '').trim().toLowerCase()) : [])
  const hasLunch = set.has('lunch')
  const hasDinner = set.has('dinner')
  if (hasLunch && hasDinner) return '全餐'
  if (hasDinner) return '晚餐'
  if (hasLunch) return '午餐'
  return '午餐'
}

/** 管理端方案 A：「周卡 · 全餐」 */
export function formatPlanTypeDisplay(planType, periods) {
  const pt = String(planType || '次卡').trim() || '次卡'
  return `${pt} · ${mealScopeLabelFromPeriods(periods)}`
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

/** 周/月卡次数用尽：balance=0 且曾有起送日或累计总次数（与后台 inactive_only 口径一致） */
export function memberCardExpired(raw, balance = null) {
  if (!raw || typeof raw !== 'object') return false
  const bal = balance != null ? Number(balance) || 0 : Number(raw.balance) || 0
  if (bal > 0) return false
  const ds = raw.delivery_start_date
  if (ds != null && String(ds).trim()) return true
  const mqt = Number(raw.meal_quota_total)
  return Number.isFinite(mqt) && mqt > 0
}

/**
 * 会员状态展示：优先使用后端 lifecycle_label（只读，不改档案）。
 * overlays 中「请假中」「待续费」覆盖主标签，与 member_lifecycle_service 一致。
 */
export function resolveMemberStatusFromLifecycle(raw, balance = null) {
  if (!raw || typeof raw !== 'object') return '未开卡'
  const overlays = Array.isArray(raw.lifecycle_overlays) ? raw.lifecycle_overlays : []
  if (overlays.includes('请假中')) return '请假中'
  if (overlays.includes('待续费')) return '待续费'

  const label =
    raw.lifecycle_label != null && String(raw.lifecycle_label).trim()
      ? String(raw.lifecycle_label).trim()
      : ''
  if (label) return label

  // 兼容未返回 lifecycle 的旧响应（兜底，不影响档案）
  const bal = balance != null ? Number(balance) || 0 : Number(raw.balance) || 0
  const active = raw.is_active !== false
  const deferred = raw.delivery_deferred === true
  const onLeaveToday = raw.is_on_leave_today === true
  const membershipRefundedAt =
    raw.membership_refunded_at != null && String(raw.membership_refunded_at).trim()
      ? String(raw.membership_refunded_at).trim()
      : null
  if (membershipRefundedAt) return '已退款'
  if (deferred) return '已暂停'
  if (active && onLeaveToday) return '请假中'
  if (memberCardExpired(raw, bal) || (active && bal === 0)) return '已过期'
  if (!active) return '未开卡'
  if (bal <= 2) return '待续费'
  return '配送中'
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
      map_location_text: '',
      door_detail: '',
      plan: '次卡',
      planBase: '次卡',
      entitled_meal_periods: [],
      meal_scope_label: '午餐',
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
      membership_refunded_at: null,
      store_pickup: false,
      skip_subscription_saturday: false,
      updated_at: '',
    }
  }
  const balance = Number(raw.balance) || 0
  const active = raw.is_active !== false
  const deferred = raw.delivery_deferred === true
  const onLeaveToday = raw.is_on_leave_today === true
  const tomorrowLeave = raw.is_leaved_tomorrow === true
  const membershipRefundedAt =
    raw.membership_refunded_at != null && String(raw.membership_refunded_at).trim()
      ? String(raw.membership_refunded_at).trim()
      : null

  const status = resolveMemberStatusFromLifecycle(raw, balance)

  const planBase = raw.plan_type || '次卡'
  const entitledPeriods = Array.isArray(raw.entitled_meal_periods) ? raw.entitled_meal_periods : []
  const plan =
    (raw.plan_type_display && String(raw.plan_type_display).trim()) ||
    formatPlanTypeDisplay(planBase, entitledPeriods)
  const totalQuota = planDefaultTotal(planBase)
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
    map_location_text: typeof raw.map_location_text === 'string' ? raw.map_location_text : '',
    door_detail: typeof raw.door_detail === 'string' ? raw.door_detail : '',
    plan,
    planBase,
    entitled_meal_periods: entitledPeriods,
    meal_scope_label:
      (raw.meal_scope_label && String(raw.meal_scope_label).trim()) ||
      mealScopeLabelFromPeriods(entitledPeriods),
    dinner_balance: Number(raw.dinner_balance) || 0,
    dinner_meal_quota_total: Number(raw.dinner_meal_quota_total) || 0,
    dinner_is_leaved_tomorrow: raw.dinner_is_leaved_tomorrow === true,
    dinner_tomorrow_leave_target_date: adminUserYmd(raw.dinner_tomorrow_leave_target_date),
    dinner_leave_range_start: adminUserYmd(raw.dinner_leave_range_start),
    dinner_leave_range_end: adminUserYmd(raw.dinner_leave_range_end),
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
    lifecycle_code:
      raw.lifecycle_code != null && String(raw.lifecycle_code).trim()
        ? String(raw.lifecycle_code).trim()
        : '',
    lifecycle_label:
      raw.lifecycle_label != null && String(raw.lifecycle_label).trim()
        ? String(raw.lifecycle_label).trim()
        : '',
    lifecycle_overlays: Array.isArray(raw.lifecycle_overlays) ? raw.lifecycle_overlays : [],
    setup_alert: raw.setup_alert === true,
    membership_refunded_at: membershipRefundedAt,
    store_pickup: raw.store_pickup === true,
    skip_subscription_saturday: raw.skip_subscription_saturday === true,
    updated_at: raw.updated_at != null ? String(raw.updated_at).trim() : '',
  }
}
