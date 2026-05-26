import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  ADMIN_TAB_COMPONENT_NAMES,
  ADMIN_TABS_MAX_CACHE,
  ADMIN_DELIVERY_WORKBENCH_TRIAD,
} from '../constants/adminTabComponents.js'

/**
 * @typedef {{ name: string, path: string, title: string, componentName: string }} AdminTab
 */

export const useAdminTabsStore = defineStore('adminTabs', () => {
  /** @type {import('vue').Ref<AdminTab[]>} */
  const tabs = ref([])

  const cachedComponentNames = computed(() =>
    tabs.value.map((t) => t.componentName).filter(Boolean),
  )

  /**
   * KeepAlive + 浏览器负担：超限则丢弃最早打开且非当前的标签
   * @param {string} pinnedRouteName 当前路由 name，尽量不关闭
   */
  function enforceMaxTabs(pinnedRouteName) {
    while (tabs.value.length > ADMIN_TABS_MAX_CACHE) {
      const drop = tabs.value.find((t) => t.name !== pinnedRouteName)
      if (!drop) break
      tabs.value = tabs.value.filter((t) => t.name !== drop.name)
    }
  }

  /**
   * 从路由名解析标签元信息（不写死标题，沿用 meta.title）
   * @param {import('vue-router').Router} router
   * @param {string} routeName
   * @returns {AdminTab | null}
   */
  function tabMetaFromRouteName(router, routeName) {
    const componentName = ADMIN_TAB_COMPONENT_NAMES[routeName]
    if (!componentName) return null
    const loc = router.resolve({ name: routeName })
    const last = loc.matched[loc.matched.length - 1]
    const title =
      last?.meta?.title != null && String(last.meta.title).trim() !== ''
        ? String(last.meta.title).trim()
        : routeName
    return { name: routeName, path: loc.fullPath, title, componentName }
  }

  /**
   * 进入配送工作台三联之一时：补齐另外两个顶栏 Tab，并排置于最前。
   * @param {import('vue-router').Router} router
   * @param {string} activeRouteName
   */
  function ensureDeliveryWorkbenchTriad(router, activeRouteName) {
    const triad = ADMIN_DELIVERY_WORKBENCH_TRIAD
    if (!triad.includes(activeRouteName)) return

    for (const n of triad) {
      if (tabs.value.some((t) => t.name === n)) continue
      const row = tabMetaFromRouteName(router, n)
      if (row) tabs.value.push(row)
    }

    const triadSet = new Set(triad)
    const byName = new Map(tabs.value.map((t) => [t.name, t]))
    const triadTabs = triad.map((n) => byName.get(n)).filter(Boolean)
    const rest = tabs.value.filter((t) => !triadSet.has(t.name))
    tabs.value = [...triadTabs, ...rest]

    enforceMaxTabs(activeRouteName)
  }

  /**
   * @param {import('vue-router').RouteLocationNormalizedLoaded} route
   */
  function openFromRoute(route) {
    const routeName = route.name
    if (typeof routeName !== 'string') return
    const componentName = ADMIN_TAB_COMPONENT_NAMES[routeName]
    if (!componentName) return

    const title =
      route.meta?.title != null && String(route.meta.title).trim() !== ''
        ? String(route.meta.title).trim()
        : routeName
    const path = route.fullPath

    const existing = tabs.value.find((t) => t.name === routeName)
    if (existing) {
      existing.path = path
      existing.title = title
      return
    }

    tabs.value.push({ name: routeName, path, title, componentName })
    enforceMaxTabs(routeName)
  }

  /**
   * @param {string} routeName
   * @param {import('vue-router').Router} router
   */
  function closeTab(routeName, router) {
    const idx = tabs.value.findIndex((t) => t.name === routeName)
    if (idx === -1) return

    const isActive = router.currentRoute.value.name === routeName
    tabs.value.splice(idx, 1)

    if (!isActive) return

    if (tabs.value.length) {
      const next = tabs.value[Math.min(idx, tabs.value.length - 1)]
      void router.push(next.path)
      return
    }

    void router.push('/')
  }

  /**
   * @param {string} path
   * @param {import('vue-router').Router} router
   */
  function activateTab(path, router) {
    if (router.currentRoute.value.fullPath === path) return
    void router.push(path)
  }

  function reset() {
    tabs.value = []
  }

  return {
    tabs,
    cachedComponentNames,
    openFromRoute,
    ensureDeliveryWorkbenchTriad,
    closeTab,
    activateTab,
    reset,
  }
})
