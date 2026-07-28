/**
 * 租户小程序独立页：解析路由 tenantId、统一鉴权错误处理。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from './useToast.js'
import { createTenantMiniProgramApi } from './useTenantMiniProgramApi.js'

export function useTenantMiniProgramPage() {
  const route = useRoute()
  const router = useRouter()

  const tenantId = computed(() => {
    const raw = route.params.tenantId
    const n = Math.floor(Number(raw))
    return Number.isFinite(n) && n >= 1 ? n : null
  })

  const tenantName = computed(() => String(route.query.name || '').trim() || `租户 #${tenantId.value || '?'}`)

  const api = computed(() => (tenantId.value != null ? createTenantMiniProgramApi(tenantId.value) : null))

  function backToTenants() {
    void router.push({ name: 'system-tenants' })
  }

  /** @returns {boolean} 是否已处理（401 登出） */
  function handleAuthError(e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return true
    }
    return false
  }

  function toastError(e, fallback) {
    if (handleAuthError(e)) return
    showToast(e instanceof Error ? e.message : fallback, 'error')
  }

  function ensureReady() {
    if (!adminAccessToken.value) {
      void router.replace({ name: 'login', query: { redirect: route.fullPath } })
      return false
    }
    if (tenantId.value == null) {
      showToast('租户 ID 无效', 'error')
      backToTenants()
      return false
    }
    return true
  }

  return {
    route,
    router,
    tenantId,
    tenantName,
    api,
    backToTenants,
    handleAuthError,
    toastError,
    ensureReady,
  }
}
