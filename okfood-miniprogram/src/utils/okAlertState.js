import { ref } from 'vue'

/** @typedef {object} OkAlertOptions
 * @property {string} [title]
 * @property {string} [content]
 * @property {boolean} [showCancel]
 * @property {string} [cancelText]
 * @property {string} [confirmText]
 * @property {boolean} [confirmDanger]
 * @property {'default'|'success'|'warning'} [tone]
 * @property {boolean} [maskClosable]
 */

export const okAlertVisible = ref(false)

/** @type {import('vue').Ref<OkAlertOptions|null>} */
export const okAlertOptions = ref(null)

/** @type {import('vue').Ref<number|null>} */
export const okAlertActiveHostId = ref(null)

/** @type {Array<{ options: OkAlertOptions, resolve: (res: { confirm?: boolean, cancel?: boolean }) => void }>} */
const pendingQueue = []

/** @type {((res: { confirm?: boolean, cancel?: boolean }) => void)|null} */
let pendingResolve = null

/** @type {Set<number>} */
const mountedHosts = new Set()

/** @type {Map<string, number>} */
const routeHostMap = new Map()

/** @type {Map<number, string>} */
const hostRouteMap = new Map()

/** @type {number|null} App 级唯一 Host，避免 Tab 页 Host 未激活导致弹窗延迟到其他页 */
let globalHostId = null

function pickHostIdForRoute(route) {
  if (globalHostId != null && mountedHosts.has(globalHostId)) {
    return globalHostId
  }
  if (route) {
    const hostId = routeHostMap.get(route)
    if (hostId != null && mountedHosts.has(hostId)) return hostId
  }
  return null
}

function resolveCurrentPageRoute() {
  const pages = getCurrentPages()
  const page = pages[pages.length - 1]
  return page?.route ? String(page.route) : ''
}

/** 当前页是否已有可展示自定义弹窗的 Host（Tab 页「我的」等） */
export function isOkAlertHostReadyForCurrentPage() {
  return pickHostIdForRoute(resolveCurrentPageRoute()) != null
}

/** 弹窗展示中不切换 Host，避免按钮事件落到不可见层 */
export function syncOkAlertHostToCurrentPage() {
  const route = resolveCurrentPageRoute()
  const hostId = pickHostIdForRoute(route)
  if (okAlertVisible.value) {
    // 弹窗若挂在其它页 Host，当前 Tab 看不见；切页时清掉，避免在订单/购卡页误弹
    if (hostId != null && okAlertActiveHostId.value !== hostId) {
      const resolve = pendingResolve
      pendingResolve = null
      closeOkAlert()
      if (resolve) resolve({ confirm: false, cancel: true })
    }
    return
  }
  okAlertActiveHostId.value = hostId
}

/** @param {OkAlertOptions} options */
export function openOkAlert(options) {
  okAlertOptions.value = { ...options }
  okAlertVisible.value = true
}

export function closeOkAlert() {
  okAlertVisible.value = false
}

/** App.vue 挂载的全局 Host：任意页面 showOkAlert 均立即在此展示 */
export function registerGlobalOkAlertHost(hostId) {
  mountedHosts.add(hostId)
  globalHostId = hostId
  okAlertActiveHostId.value = hostId
  tryFlushOkAlertQueue()
}

/** @param {number} hostId */
export function unregisterGlobalOkAlertHost(hostId) {
  mountedHosts.delete(hostId)
  if (globalHostId === hostId) {
    globalHostId = null
  }
  if (okAlertActiveHostId.value === hostId) {
    syncOkAlertHostToCurrentPage()
  }
  tryFlushOkAlertQueue()
}

/**
 * @param {number} hostId
 * @param {string} [route] 所属页面 route，用于按当前页激活 Host
 */
export function registerOkAlertHost(hostId, route = '') {
  mountedHosts.add(hostId)
  const r = String(route || '').trim()
  if (r) {
    routeHostMap.set(r, hostId)
    hostRouteMap.set(hostId, r)
  }
  syncOkAlertHostToCurrentPage()
  tryFlushOkAlertQueue()
}

/** @param {number} hostId */
export function unregisterOkAlertHost(hostId) {
  mountedHosts.delete(hostId)
  const r = hostRouteMap.get(hostId)
  if (r) routeHostMap.delete(r)
  hostRouteMap.delete(hostId)
  if (okAlertActiveHostId.value === hostId) {
    syncOkAlertHostToCurrentPage()
  }
  tryFlushOkAlertQueue()
}

/** @param {number} hostId 当前页切到前台时激活对应 Host */
export function activateOkAlertHost(hostId, route = '') {
  if (!mountedHosts.has(hostId)) return
  const r = String(route || resolveCurrentPageRoute()).trim()
  if (r) {
    routeHostMap.set(r, hostId)
    hostRouteMap.set(hostId, r)
  }
  if (okAlertVisible.value) return
  okAlertActiveHostId.value = hostId
  tryFlushOkAlertQueue()
}

/**
 * @param {OkAlertOptions} options
 * @param {(res: { confirm?: boolean, cancel?: boolean }) => void} resolve
 * @returns {boolean} 是否已由自定义弹窗接管
 */
function dispatchAlert(options, resolve) {
  if (okAlertVisible.value || pendingResolve) {
    pendingQueue.push({ options, resolve })
    return true
  }
  syncOkAlertHostToCurrentPage()
  if (okAlertActiveHostId.value == null) {
    return false
  }
  pendingResolve = resolve
  openOkAlert(options)
  return true
}

export function tryFlushOkAlertQueue() {
  if (okAlertVisible.value || pendingResolve) return
  syncOkAlertHostToCurrentPage()
  if (okAlertActiveHostId.value == null) return
  const next = pendingQueue.shift()
  if (!next) return
  if (!dispatchAlert(next.options, next.resolve)) {
    pendingQueue.unshift(next)
  }
}

/** @param {{ confirm?: boolean, cancel?: boolean }} res */
export function finishOkAlert(res) {
  const resolve = pendingResolve
  pendingResolve = null
  closeOkAlert()
  if (resolve) resolve(res)
  tryFlushOkAlertQueue()
}

/** @param {OkAlertOptions} options */
export function requestOkAlert(options) {
  return new Promise((resolve) => {
    if (!dispatchAlert(options, resolve)) {
      resolve(null)
    }
  })
}
