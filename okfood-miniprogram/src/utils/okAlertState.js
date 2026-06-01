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

/** @param {OkAlertOptions} options */
export function openOkAlert(options) {
  okAlertOptions.value = { ...options }
  okAlertVisible.value = true
}

export function closeOkAlert() {
  okAlertVisible.value = false
}

/** @type {Set<number>} */
const mountedHosts = new Set()

/** @param {number} hostId */
export function registerOkAlertHost(hostId) {
  mountedHosts.add(hostId)
  okAlertActiveHostId.value = hostId
  tryFlushQueue()
}

/** @param {number} hostId */
export function unregisterOkAlertHost(hostId) {
  mountedHosts.delete(hostId)
  if (okAlertActiveHostId.value === hostId) {
    const remaining = [...mountedHosts]
    okAlertActiveHostId.value = remaining.length ? Math.max(...remaining) : null
  }
  tryFlushQueue()
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
  pendingResolve = resolve
  openOkAlert(options)
}

function tryFlushQueue() {
  if (okAlertActiveHostId.value == null || okAlertVisible.value || pendingResolve) return
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
    if (okAlertActiveHostId.value == null) {
      pendingQueue.push({ options, resolve })
      return
    }
    dispatchAlert(options, resolve)
  })
}
