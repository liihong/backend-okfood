import { ref, computed } from 'vue'

/**
 * 登录表单预填：仅本地 .env 可选配置，勿把真实密码提交到仓库。
 */
export const LOGIN_PRESET_USER = String(import.meta.env.VITE_ADMIN_LOGIN_PRESET_USER ?? '').trim()
export const LOGIN_PRESET_PASSWORD = String(
  import.meta.env.VITE_ADMIN_LOGIN_PRESET_PASSWORD ?? '',
).trim()
export const ADMIN_TOKEN_KEY = 'okfood_admin_access_token'
const ENV_API_BASE = String(import.meta.env.VITE_API_BASE_URL || '').trim()
export const API_BASE = ENV_API_BASE.replace(/\/$/, '')

export const adminAccessToken = ref('')
export const rememberLogin = ref(false)
/** 会员列表：会员档案页写入，营业概览预览读取 */
export const memberList = ref([])

export const isLoggedIn = computed(() => Boolean(String(adminAccessToken.value || '').trim()))

/** @type {import('vue-router').Router | null} */
let adminRouter = null

/** @param {import('vue-router').Router} r */
export function registerAdminRouter(r) {
  adminRouter = r
}

export function hydrateTokenFromStorage() {
  try {
    const fromLocal = localStorage.getItem(ADMIN_TOKEN_KEY)
    const fromSess = sessionStorage.getItem(ADMIN_TOKEN_KEY)
    adminAccessToken.value = (fromLocal || fromSess || '').trim()
    rememberLogin.value = Boolean(fromLocal)
  } catch {
    /* ignore */
  }
}

export function setAdminToken(token) {
  adminAccessToken.value = token
  try {
    if (rememberLogin.value) {
      localStorage.setItem(ADMIN_TOKEN_KEY, token)
      sessionStorage.removeItem(ADMIN_TOKEN_KEY)
    } else {
      sessionStorage.setItem(ADMIN_TOKEN_KEY, token)
      localStorage.removeItem(ADMIN_TOKEN_KEY)
    }
  } catch {
    /* ignore */
  }
}

export function clearAdminToken() {
  adminAccessToken.value = ''
  try {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY)
    localStorage.removeItem(ADMIN_TOKEN_KEY)
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

/** 月卡 / 周卡周期默认总次数（与充值选项一致） */
export function planDefaultTotal(planType) {
  if (planType === '月卡') return 24
  if (planType === '周卡') return 6
  return null
}

/** GET /api/admin/users 单条映射为表格行 */
export function mapAdminUserToRow(raw, idx) {
  const balance = Number(raw.balance) || 0
  const active = raw.is_active !== false
  const onLeaveToday = raw.is_on_leave_today === true
  const tomorrowLeave = raw.is_leaved_tomorrow === true

  let status = '活跃中'
  if (!active) status = '未开卡'
  else if (onLeaveToday) status = '请假中'
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

  return {
    id: raw.id != null ? raw.id : raw.phone || `row-${idx}`,
    name: raw.name || '—',
    phone: raw.phone || '',
    balance,
    balanceLabel,
    totalQuota,
    area: raw.area || '—',
    address: raw.address || '',
    detail_address: typeof raw.detail_address === 'string' ? raw.detail_address : '',
    plan,
    remarks: raw.remarks ?? '',
    daily_meal_units: Math.max(1, Math.min(50, Number(raw.daily_meal_units) || 1)),
    meal_quota_total: hasPersistedTotal ? mealQuotaTotal : 0,
    wechat_name: raw.wechat_name ?? '',
    is_active: active,
    is_on_leave_today: onLeaveToday,
    tomorrow_leave: active && !onLeaveToday && tomorrowLeave,
    status,
  }
}
