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

function resolveCurrentPageRoute() {
  const pages = getCurrentPages()
  const page = pages[pages.length - 1]
  return page?.route ? String(page.route) : ''
}

/** 弹窗展示中不切换 Host，避免按钮事件落到不可见层 */
export function syncOkAlertHostToCurrentPage() {
  if (okAlertVisible.value) return
  const route = resolveCurrentPageRoute()
  const hostId = route ? routeHostMap.get(route) : undefined
  if (hostId != null) {
    okAlertActiveHostId.value = hostId
    return
  }
  if (mountedHosts.size) {
    okAlertActiveHostId.value = Math.max(...mountedHosts)
  } else {
    okAlertActiveHostId.value = null
  }
}

/** @param {OkAlertOptions} options */
export function openOkAlert(options) {
  okAlertOptions.value = { ...options }
  okAlertVisible.value = true
}

export function closeOkAlert() {
  okAlertVisible.value = false
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
  tryFlushQueue()
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
  tryFlushQueue()
}

/** @param {number} hostId 当前页切到前台时激活对应 Host */
export function activateOkAlertHost(hostId) {
  if (!mountedHosts.has(hostId)) return
  if (okAlertVisible.value) return
  okAlertActiveHostId.value = hostId
}

/**
 * @param {OkAlertOptions} options
 * @param {(res: { confirm?: boolean, cancel?: boolean }) => void} resolve
 */
function dispatchAlert(options, resolve) {
  if (okAlertVisible.value || pendingResolve) {
    pendingQueue.push({ options, resolve })
    return
  }
  syncOkAlertHostToCurrentPage()
  if (okAlertActiveHostId.value == null) {
    pendingQueue.push({ options, resolve })
    return
  }
  pendingResolve = resolve
  openOkAlert(options)
}

function tryFlushQueue() {
  if (okAlertVisible.value || pendingResolve) return
  if (okAlertActiveHostId.value == null && mountedHosts.size === 0) return
  if (okAlertActiveHostId.value == null) syncOkAlertHostToCurrentPage()
  if (okAlertActiveHostId.value == null) return
  const next = pendingQueue.shift()
  if (!next) return
  dispatchAlert(next.options, next.resolve)
}

/** @param {{ confirm?: boolean, cancel?: boolean }} res */
export function finishOkAlert(res) {
  const resolve = pendingResolve
  pendingResolve = null
  closeOkAlert()
  if (resolve) resolve(res)
  tryFlushQueue()
}

/** @param {OkAlertOptions} options */
export function requestOkAlert(options) {
  return new Promise((resolve) => {
    if (mountedHosts.size === 0) {
      pendingQueue.push({ options, resolve })
      return
    }
    dispatchAlert(options, resolve)
  })
}
