import { ref, computed } from 'vue'
import { apiJson, adminAccessToken } from '../admin/core.js'
import {
  handleRetailOrderNotifications,
  resetRetailOrderVoiceAlertState,
} from './useRetailOrderVoiceAlert.js'

const notifications = ref([])
const unacknowledgedCount = ref(0)
const loading = ref(false)
const acknowledgingId = ref(null)

/** 页面可见时 30s 轮询，便于零售新单语音提醒；后台标签页 2min */
const POLL_INTERVAL_VISIBLE_MS = 30 * 1000
const POLL_INTERVAL_HIDDEN_MS = 2 * 60 * 1000

let pollTimer = null
let subscriberCount = 0
let pollIntervalMs = POLL_INTERVAL_VISIBLE_MS

export function useAdminSystemNotifications() {
  const hasUnread = computed(() => unacknowledgedCount.value > 0)
  const unreadItems = computed(() =>
    notifications.value.filter((n) => !n.acknowledged_at),
  )

  async function fetchNotifications({ silent = false } = {}) {
    if (!String(adminAccessToken.value || '').trim()) {
      notifications.value = []
      unacknowledgedCount.value = 0
      return
    }
    if (!silent) loading.value = true
    try {
      const data = await apiJson(
        '/api/admin/system-notifications?unacknowledged_only=true&limit=50',
        {},
        { auth: true },
      )
      const items = Array.isArray(data?.items) ? data.items : []
      notifications.value = items
      unacknowledgedCount.value =
        Number(data?.unacknowledged_count) || items.length
      handleRetailOrderNotifications(items)
    } catch {
      if (!silent) {
        notifications.value = []
        unacknowledgedCount.value = 0
      }
    } finally {
      if (!silent) loading.value = false
    }
  }

  async function acknowledgeNotification(id) {
    const nid = Number(id)
    if (!Number.isFinite(nid) || nid <= 0) return false
    acknowledgingId.value = nid
    try {
      await apiJson(
        `/api/admin/system-notifications/${nid}/acknowledge`,
        { method: 'POST' },
        { auth: true },
      )
      await fetchNotifications({ silent: true })
      return true
    } catch {
      return false
    } finally {
      acknowledgingId.value = null
    }
  }

  function startPolling(intervalMs = 5 * 60 * 1000) {
    if (pollTimer != null) return
    pollTimer = window.setInterval(() => {
      fetchNotifications({ silent: true })
    }, intervalMs)
  }

  function stopPolling() {
    if (pollTimer == null) return
    window.clearInterval(pollTimer)
    pollTimer = null
  }

  function subscribeLayoutPolling() {
    subscriberCount += 1
    if (subscriberCount === 1) {
      fetchNotifications()
      startPolling()
    }
  }

  function unsubscribeLayoutPolling() {
    subscriberCount = Math.max(0, subscriberCount - 1)
    if (subscriberCount === 0) {
      stopPolling()
    }
  }

  return {
    notifications,
    unacknowledgedCount,
    hasUnread,
    unreadItems,
    loading,
    acknowledgingId,
    fetchNotifications,
    acknowledgeNotification,
    subscribeLayoutPolling,
    unsubscribeLayoutPolling,
  }
}
