/**
 * API 根（无末尾 /，路径自带 /api/...）。
 * 默认：`dev` 为本机 8001；`build` 为线上。
 * 真机预览 dev 包时本机请设环境变量 `VITE_API_BASE=http://127.0.0.1:8001`（127.0.0.1 指向手机自身，会请求失败/超时）。
 */
const viteApiBase =
  typeof import.meta.env.VITE_API_BASE === 'string'
    ? import.meta.env.VITE_API_BASE.trim().replace(/\/$/, '')
    : ''
export const API_BASE =
  viteApiBase ||
  (import.meta.env.DEV ? 'https://ok.sourcefire.cn' : 'https://ok.sourcefire.cn')

/** 默认超时（ms）。可在 request(path, { timeout })覆盖；弱网可适当加大 */
export const DEFAULT_REQUEST_TIMEOUT_MS = 120000

const MEMBER_TOKEN_KEY = 'okfood_member_token'
const COURIER_TOKEN_KEY = 'okfood_courier_token'
/** 配送员登录手机号（仅本地缓存，用于预填与快速验证；与会员 token 独立） */
const COURIER_PHONE_KEY = 'okfood_courier_phone'
/** 上次使用的端：member | courier（仅本地；删小程序即清空） */
const APP_USER_MODE_KEY = 'okfood_app_user_mode'
/** GET /api/courier/me 最近一次成功结果（仅本地，随骑手 token 清除） */
const COURIER_ME_CACHE_KEY = 'okfood_courier_me_cache'

/**
 * 若本地标记为配送员端，从会员首页/「我的」等入口兜底跳转（reLaunch 清空页面栈，避免自定义 tab 与 switchTab 竞态）。
 * @returns {boolean} 是否已发起 reLaunch
 */
export function reLaunchIfCourierModePreferred() {
  if (getAppUserMode() !== 'courier') return false
  if (getCourierToken()) {
    uni.reLaunch({ url: '/pages/courier/home' })
    return true
  }
  uni.reLaunch({ url: '/pages/courier/login' })
  return true
}

/**
 * @returns {'member' | 'courier'}
 */
export function getAppUserMode() {
  try {
    return uni.getStorageSync(APP_USER_MODE_KEY) === 'courier'
      ? 'courier'
      : 'member'
  } catch {
    return 'member'
  }
}

/**
 * @param {'member' | 'courier'} mode
 */
export function setAppUserMode(mode) {
  try {
    if (mode === 'courier') uni.setStorageSync(APP_USER_MODE_KEY, 'courier')
    else uni.setStorageSync(APP_USER_MODE_KEY, 'member')
  } catch {
    /* ignore */
  }
}

/**
 * @param {unknown} e uni.request fail 参数等
 * @returns {Error}
 */
function normalizeRequestFail(e) {
  /** @param {unknown} cause */
  function timeoutErr(cause) {
    const err = new Error('请求超时，请检查网络后重试')
    err.cause = cause
    return err
  }
  /** @param {unknown} cause */
  function abortErr(cause) {
    const err = new Error('请求已取消')
    err.cause = cause
    return err
  }

  // 微信端部分基础库 fail 只给字符串 "timeout"，原先会 new Error('timeout')，界面/控制台都不友好
  if (typeof e === 'string') {
    const t = e.trim()
    if (/timeout/i.test(t) || t === '超时') return timeoutErr(e)
    if (/abort/i.test(t)) return abortErr(e)
    return Object.assign(new Error(t || '网络请求失败'), { cause: e })
  }
  if (e instanceof Error) {
    const m = e.message || ''
    if (/timeout/i.test(m) || /超时/.test(m)) return timeoutErr(e)
    if (/abort/i.test(m)) return abortErr(e)
    return Object.assign(new Error(m || '网络请求失败'), { cause: e })
  }

  const raw = e && typeof e === 'object' ? e : {}
  const errMsg = typeof raw.errMsg === 'string' ? raw.errMsg : ''
  const message = typeof raw.message === 'string' ? raw.message : ''
  const combined = `${errMsg} ${message}`.trim()
  if (/timeout/i.test(combined) || /超时/.test(combined)) return timeoutErr(e)
  if (/abort/i.test(combined)) return abortErr(e)
  const fallback = errMsg || message || '网络请求失败'
  return Object.assign(new Error(fallback), { cause: e })
}

export function getMemberToken() {
  try {
    return uni.getStorageSync(MEMBER_TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function getCourierToken() {
  try {
    return uni.getStorageSync(COURIER_TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setCourierToken(token) {
  try {
    if (token) uni.setStorageSync(COURIER_TOKEN_KEY, token)
    else {
      uni.removeStorageSync(COURIER_TOKEN_KEY)
      uni.removeStorageSync(COURIER_ME_CACHE_KEY)
    }
  } catch {
    /* ignore */
  }
}

/**
 * @param {object | null | undefined} me courier /me 接口返回体
 */
export function setCourierMeCache(me) {
  try {
    if (me && typeof me === 'object') {
      uni.setStorageSync(COURIER_ME_CACHE_KEY, JSON.stringify(me))
    } else {
      uni.removeStorageSync(COURIER_ME_CACHE_KEY)
    }
  } catch {
    /* ignore */
  }
}

/** @returns {Record<string, unknown> | null} */
export function getCourierMeCache() {
  try {
    const raw = uni.getStorageSync(COURIER_ME_CACHE_KEY)
    if (!raw) return null
    const o = JSON.parse(raw)
    return o && typeof o === 'object' ? o : null
  } catch {
    return null
  }
}

export function clearCourierToken() {
  setCourierToken('')
}

export function getCourierPhone() {
  try {
    return uni.getStorageSync(COURIER_PHONE_KEY) || ''
  } catch {
    return ''
  }
}

/**
 * @param {string} [rawPhone] 11 位数字；传空字符串则清除缓存
 */
export function setCourierPhone(rawPhone) {
  try {
    const d = String(rawPhone || '').replace(/\D/g, '')
    if (d.length === 11) uni.setStorageSync(COURIER_PHONE_KEY, d)
    else uni.removeStorageSync(COURIER_PHONE_KEY)
  } catch {
    /* ignore */
  }
}

/** 部分环境下 res.data 为 JSON 字符串，需先解析 */
function parseResponsePayload(raw) {
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw)
    } catch {
      return raw
    }
  }
  return raw
}

/**
 * @param {string} path 如 /api/menu/tomorrow
 * @param {UniNamespace.RequestOptions & { retry?: number }} options
 * `retry`：仅在网络超时（归一化后的「请求超时…」）时额外重试次数，默认 0；建议 GET 且幂等接口使用，最大 3。
 */
export function request(path, options = {}) {
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
  const header = {
    'Content-Type': 'application/json',
    ...(options.header || {}),
  }
  const token = getMemberToken()
  if (token) header.Authorization = `Bearer ${token}`

  const timeout =
    typeof options.timeout === 'number'
      ? options.timeout
      : DEFAULT_REQUEST_TIMEOUT_MS
  const extraRetries = Math.min(
    3,
    Math.max(0, Math.floor(Number(options.retry) || 0)),
  )

  function isTimeoutError(err) {
    return (
      err instanceof Error &&
      (err.message.includes('请求超时') || err.message.includes('超时'))
    )
  }

  function execOnce() {
    return new Promise((resolve, reject) => {
      uni.request({
        url,
        method: options.method || 'GET',
        data: options.data,
        header,
        timeout,
        success: (res) => {
          const { statusCode, data: rawData } = res
          const data = parseResponsePayload(rawData)
          if (statusCode < 200 || statusCode >= 300) {
            let msg = `请求失败 (${statusCode})`
            if (data && typeof data === 'object') {
              if (typeof data.msg === 'string' && data.msg) msg = data.msg
              else if (typeof data.message === 'string' && data.message) msg = data.message
              else if (typeof data.detail === 'string') msg = data.detail
            }
            const err = new Error(msg)
            err.status = statusCode
            reject(err)
            return
          }
          if (data && typeof data === 'object' && !Array.isArray(data) && 'code' in data) {
            const c = Number(data.code)
            if (c === 200) {
              if (data.data !== undefined) {
                resolve(data.data)
              } else {
                const { code: _c, message: _m, msg: _msg, detail: _d, ...rest } = data
                resolve(Object.keys(rest).length ? rest : data)
              }
              return
            }
            const bizMsg =
              c === 404
                ? (typeof data.msg === 'string' && data.msg) ||
                  (typeof data.message === 'string' && data.message) ||
                  (typeof data.detail === 'string' && data.detail) ||
                  `业务错误 (${c})`
                : (typeof data.message === 'string' && data.message) ||
                  (typeof data.msg === 'string' && data.msg) ||
                  (typeof data.detail === 'string' && data.detail) ||
                  `业务错误 (${c})`
            const err = new Error(bizMsg)
            err.status = statusCode
            err.bizCode = c
            reject(err)
            return
          }
          resolve(data)
        },
        fail: (e) => reject(normalizeRequestFail(e)),
      })
    })
  }

  async function run(remainingExtraAttempts) {
    try {
      return await execOnce()
    } catch (err) {
      if (isTimeoutError(err) && remainingExtraAttempts > 0) {
        return run(remainingExtraAttempts - 1)
      }
      throw err
    }
  }

  return run(extraRetries)
}

/**
 * 会员头像 multipart上传：服务端写入阿里云 OSS（未配置 OSS 时落本地），返回可写入 avatar_url 的地址。
 * @param {string} filePath 本地临时路径（如 chooseAvatar）
 * @param {{ timeout?: number }} [options]
 * @returns {Promise<string>}
 */
export function uploadMemberAvatarFile(filePath, options = {}) {
  const url = `${API_BASE}/api/user/me/avatar`
  const token = getMemberToken()
  const header = {}
  if (token) header.Authorization = `Bearer ${token}`
  const timeout =
    typeof options.timeout === 'number'
      ? options.timeout
      : DEFAULT_REQUEST_TIMEOUT_MS

  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url,
      filePath,
      name: 'file',
      header,
      timeout,
      success: (res) => {
        const { statusCode, data: rawData } = res
        const data = parseResponsePayload(rawData)
        if (statusCode < 200 || statusCode >= 300) {
          let msg = `请求失败 (${statusCode})`
          if (data && typeof data === 'object') {
            if (typeof data.msg === 'string' && data.msg) msg = data.msg
            else if (typeof data.message === 'string' && data.message) msg = data.message
            else if (typeof data.detail === 'string') msg = data.detail
          }
          reject(new Error(msg))
          return
        }
        if (data && typeof data === 'object' && !Array.isArray(data) && 'code' in data) {
          const c = Number(data.code)
          if (c === 200 && data.data && typeof data.data.url === 'string') {
            resolve(data.data.url.trim())
            return
          }
          const bizMsg =
            (typeof data.message === 'string' && data.message) ||
            (typeof data.msg === 'string' && data.msg) ||
            (typeof data.detail === 'string' && data.detail) ||
            `上传失败 (${c})`
          reject(new Error(bizMsg))
          return
        }
        reject(new Error('上传响应格式异常'))
      },
      fail: (e) => reject(normalizeRequestFail(e)),
    })
  })
}

/**
 * 配送员端请求：使用骑手 JWT，不传会员 token。
 * @param {string} path
 * @param {UniNamespace.RequestOptions & { retry?: number, skipAuth?: boolean }} options
 */
export function courierRequest(path, options = {}) {
  const url = `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
  const header = {
    'Content-Type': 'application/json',
    ...(options.header || {}),
  }
  if (!options.skipAuth) {
    const token = getCourierToken()
    if (token) header.Authorization = `Bearer ${token}`
  }

  const timeout =
    typeof options.timeout === 'number'
      ? options.timeout
      : DEFAULT_REQUEST_TIMEOUT_MS
  const extraRetries = Math.min(
    3,
    Math.max(0, Math.floor(Number(options.retry) || 0)),
  )

  function isTimeoutError(err) {
    return (
      err instanceof Error &&
      (err.message.includes('请求超时') || err.message.includes('超时'))
    )
  }

  function execOnce() {
    return new Promise((resolve, reject) => {
      uni.request({
        url,
        method: options.method || 'GET',
        data: options.data,
        header,
        timeout,
        success: (res) => {
          const { statusCode, data: rawData } = res
          const data = parseResponsePayload(rawData)
          if (statusCode < 200 || statusCode >= 300) {
            let msg = `请求失败 (${statusCode})`
            if (data && typeof data === 'object') {
              if (typeof data.msg === 'string' && data.msg) msg = data.msg
              else if (typeof data.message === 'string' && data.message) msg = data.message
              else if (typeof data.detail === 'string') msg = data.detail
            }
            const err = new Error(msg)
            err.status = statusCode
            reject(err)
            return
          }
          if (data && typeof data === 'object' && !Array.isArray(data) && 'code' in data) {
            const c = Number(data.code)
            if (c === 200) {
              if (data.data !== undefined) {
                resolve(data.data)
              } else {
                const { code: _c, message: _m, msg: _msg, detail: _d, ...rest } = data
                resolve(Object.keys(rest).length ? rest : data)
              }
              return
            }
            const bizMsg =
              c === 404
                ? (typeof data.msg === 'string' && data.msg) ||
                  (typeof data.message === 'string' && data.message) ||
                  (typeof data.detail === 'string' && data.detail) ||
                  `业务错误 (${c})`
                : (typeof data.message === 'string' && data.message) ||
                  (typeof data.msg === 'string' && data.msg) ||
                  (typeof data.detail === 'string' && data.detail) ||
                  `业务错误 (${c})`
            const err = new Error(bizMsg)
            err.status = statusCode
            err.bizCode = c
            reject(err)
            return
          }
          resolve(data)
        },
        fail: (e) => reject(normalizeRequestFail(e)),
      })
    })
  }

  async function runCourier(remainingExtraAttempts) {
    try {
      return await execOnce()
    } catch (err) {
      if (isTimeoutError(err) && remainingExtraAttempts > 0) {
        return runCourier(remainingExtraAttempts - 1)
      }
      throw err
    }
  }

  return runCourier(extraRetries)
}
