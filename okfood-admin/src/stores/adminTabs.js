import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  ADMIN_TAB_COMPONENT_NAMES,
  ADMIN_TABS_MAX_CACHE,
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

    while (tabs.value.length > ADMIN_TABS_MAX_CACHE) {
      const drop = tabs.value.find((t) => t.name !== routeName)
      if (!drop) break
      tabs.value = tabs.value.filter((t) => t.name !== drop.name)
    }
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
    closeTab,
    activateTab,
    reset,
  }
})
