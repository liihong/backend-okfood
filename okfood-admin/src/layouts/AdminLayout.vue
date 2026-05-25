<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Users,
  Truck,
  Utensils,
  BarChart3,
  MapPin,
  DollarSign,
  LogOut,
  ClipboardList,
  Package,
  ChevronsLeft,
  ChevronsRight,
  Settings,
  X,
  Bell,
} from 'lucide-vue-next'
import {
  handleAdminLogout,
  adminKind,
  adminAccessToken,
  hydrateTokenFromStorage,
} from '../admin/core.js'
import { useAdminTabsStore } from '../stores/adminTabs.js'
import { ADMIN_TABS_MAX_CACHE } from '../constants/adminTabComponents.js'
import { useAdminSystemNotifications } from '../composables/useAdminSystemNotifications.js'
import { useToast } from '../composables/useToast.js'

const SIDEBAR_COLLAPSED_KEY = 'okfood-admin-sidebar-collapsed'

const route = useRoute()
const router = useRouter()
const tabsStore = useAdminTabsStore()
const { showToast } = useToast()
const {
  unreadItems,
  unacknowledgedCount,
  hasUnread,
  loading: notificationsLoading,
  acknowledgingId,
  acknowledgeNotification,
  subscribeLayoutPolling,
  unsubscribeLayoutPolling,
  fetchNotifications,
} = useAdminSystemNotifications()

const notificationPopoverVisible = ref(false)

const isDeliveryOnly = computed(() => adminKind.value === 'delivery')
const isSupportOnly = computed(() => adminKind.value === 'support')
const isSystemOnly = computed(() => adminKind.value === 'system')

/** 店主/配送账号展示系统消息铃铛 */
const showSystemNotifications = computed(
  () => !isSystemOnly.value && !isSupportOnly.value,
)

const notificationBadgeText = computed(() => {
  const n = Number(unacknowledgedCount.value) || 0
  if (n <= 0) return ''
  return n > 9 ? '9+' : String(n)
})

async function onAcknowledgeNotification(item) {
  const ok = await acknowledgeNotification(item?.id)
  if (ok) {
    showToast('已确认系统消息', 'success')
    if (unreadItems.value.length === 0) {
      notificationPopoverVisible.value = false
    }
  } else {
    showToast('确认失败，请稍后重试', 'error')
  }
}

function goSfMonitor(item) {
  const d = String(item?.business_date || '').trim()
  notificationPopoverVisible.value = false
  const query = d ? { delivery_date: d } : {}
  router.push({ path: '/delivery-sf-orders', query })
}

/** 与模板绑定：明确布尔，避免 Element Plus 菜单缓存旧结构 */
const showFullAdminMenus = computed(() => !isDeliveryOnly.value && !isSystemOnly.value)
/** 仅店主完整账号：财务中心、门店配置 */
const showOwnerAdminMenus = computed(
  () => !isDeliveryOnly.value && !isSupportOnly.value && !isSystemOnly.value,
)
/** 平台管理员：租户维护等 */
const showSystemAdminMenus = computed(() => isSystemOnly.value)

const portalSubtitle = computed(() => {
  if (isDeliveryOnly.value) return '配送管理'
  if (isSupportOnly.value) return '客服工作台'
  if (isSystemOnly.value) return '平台管理'
  return 'SUPER ADMIN'
})

const pageTitle = computed(() => route.meta.title || 'OK Fine Admin')

/** 顶栏主标题下可选副文案（如配送大表说明） */
const pageSubtitle = computed(() => {
  const s = route.meta.pageSubtitle
  return s != null && String(s).trim() !== '' ? String(s).trim() : ''
})

/** 配送大表：顶栏右侧挂载工具栏（Teleport 目标） */
const isDeliveryPage = computed(() => route.name === 'delivery')

/** 营业概览等页在内容区内自带头图，布局顶栏可完全省略 */
const hidePageTitle = computed(() => Boolean(route.meta.hidePageTitle))

const activeMenuPath = computed(() => route.path)

/** 桌面：侧栏收起偏好（持久化） */
const sidebarCollapsedPref = ref(false)

/** 窄屏：是否与桌面一致展开侧栏文案（默认 false = 自动窄图标栏） */
const narrowSidebarExpanded = ref(false)

const isNarrowScreen = ref(
  typeof window !== 'undefined' && window.matchMedia('(max-width: 900px)').matches,
)

let sidebarMediaQuery = null

function syncNarrowScreen() {
  if (!sidebarMediaQuery) return
  const narrow = sidebarMediaQuery.matches
  if (narrow && !isNarrowScreen.value) {
    narrowSidebarExpanded.value = false
  }
  isNarrowScreen.value = narrow
}

/** 实际是否收起侧栏：手机默认收起；桌面来自用户偏好 */
const sidebarCollapsed = computed(() =>
  isNarrowScreen.value ? !narrowSidebarExpanded.value : sidebarCollapsedPref.value,
)

function toggleSidebar() {
  if (isNarrowScreen.value) {
    narrowSidebarExpanded.value = !narrowSidebarExpanded.value
  } else {
    sidebarCollapsedPref.value = !sidebarCollapsedPref.value
  }
}

onMounted(() => {
  hydrateTokenFromStorage()
  if (showSystemNotifications.value) {
    subscribeLayoutPolling()
  }
  sidebarMediaQuery = window.matchMedia('(max-width: 900px)')
  syncNarrowScreen()
  sidebarMediaQuery.addEventListener('change', syncNarrowScreen)
  try {
    if (localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1') {
      sidebarCollapsedPref.value = true
    }
  } catch {
    /* 忽略私有模式等导致的存储异常 */
  }
})

onUnmounted(() => {
  sidebarMediaQuery?.removeEventListener('change', syncNarrowScreen)
  unsubscribeLayoutPolling()
})

watch(sidebarCollapsedPref, (v) => {
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, v ? '1' : '0')
  } catch {
    /* 同上 */
  }
})

watch(
  () => route.fullPath,
  () => {
    tabsStore.openFromRoute(route)
  },
  { immediate: true },
)

watch(
  () => adminAccessToken.value,
  (token) => {
    if (!String(token || '').trim()) {
      tabsStore.reset()
      notificationPopoverVisible.value = false
    } else if (showSystemNotifications.value) {
      fetchNotifications({ silent: true })
    }
  },
)

const openedTabs = computed(() => tabsStore.tabs)
const activeTabName = computed(() =>
  typeof route.name === 'string' ? route.name : '',
)
const keepAliveInclude = computed(() => tabsStore.cachedComponentNames)

function onTabClick(tab) {
  tabsStore.activateTab(tab.path, router)
}

function onTabClose(tab) {
  tabsStore.closeTab(tab.name, router)
}
</script>

<template>
  <div class="admin-layout" :class="{ 'admin-layout--sidebar-collapsed': sidebarCollapsed }">
    <aside class="sidebar" :class="{ 'sidebar--collapsed': sidebarCollapsed }">
      <div class="logo-area">
        <div class="logo-box">&#128076;</div>
        <div v-show="!sidebarCollapsed" class="logo-text">
          <h1>OK Fine</h1>
          <span>{{ portalSubtitle }}</span>
        </div>
        <button
          type="button"
          class="sidebar-collapse-toggle"
          :aria-label="sidebarCollapsed ? '展开侧栏菜单' : '收起侧栏菜单'"
          :aria-expanded="!sidebarCollapsed"
          @click="toggleSidebar"
        >
          <ChevronsLeft v-if="!sidebarCollapsed" :size="18" stroke-width="2" />
          <ChevronsRight v-else :size="18" stroke-width="2" />
        </button>
      </div>

      <el-menu
        :key="adminKind"
        class="sidebar-menu"
        :default-active="activeMenuPath"
        :collapse="sidebarCollapsed"
        router
        :ellipsis="false"
        background-color="transparent"
        text-color="rgba(255, 255, 255, 0.72)"
        active-text-color="#facc15"
      >
        <el-menu-item v-if="showFullAdminMenus" index="/dashboard">
          <!-- 外层必须用 div：el-menu--collapse 会把 >span 设为 width:0 隐藏，连图标一起没了 -->
          <div class="menu-item-inner">
            <BarChart3 :size="18" stroke-width="2" />
            <span class="menu-item-label">营业概览</span>
          </div>
        </el-menu-item>
        <el-menu-item v-if="showFullAdminMenus" index="/users">
          <div class="menu-item-inner">
            <Users :size="18" stroke-width="2" />
            <span class="menu-item-label">会员档案</span>
          </div>
        </el-menu-item>
        <el-menu-item v-if="showFullAdminMenus" index="/card-orders">
          <div class="menu-item-inner">
            <ClipboardList :size="18" stroke-width="2" />
            <span class="menu-item-label">开卡工单</span>
          </div>
        </el-menu-item>
        <el-menu-item v-if="showFullAdminMenus" index="/orders">
          <div class="menu-item-inner">
            <Package :size="18" stroke-width="2" />
            <span class="menu-item-label">订单管理</span>
          </div>
        </el-menu-item>
        <el-menu-item v-if="showFullAdminMenus" index="/delivery">
          <div class="menu-item-inner">
            <Truck :size="18" stroke-width="2" />
            <span class="menu-item-label">配送大表</span>
          </div>
        </el-menu-item>

        <el-sub-menu index="sub-delivery">
          <template #title>
            <div class="menu-item-inner">
              <MapPin :size="18" stroke-width="2" />
              <span class="menu-item-label">配送管理</span>
            </div>
          </template>
          <el-menu-item index="/regions">配送区域管理</el-menu-item>
          <el-menu-item index="/couriers">配送员管理</el-menu-item>
          <el-menu-item index="/delivery-sf-orders">顺丰订单监控</el-menu-item>
        </el-sub-menu>

        <el-menu-item v-if="showOwnerAdminMenus" index="/finance">
          <div class="menu-item-inner">
            <DollarSign :size="18" stroke-width="2" />
            <span class="menu-item-label">财务中心</span>
          </div>
        </el-menu-item>

        <el-sub-menu v-if="showFullAdminMenus" index="sub-menu-mgmt">
          <template #title>
            <div class="menu-item-inner">
              <Utensils :size="18" stroke-width="2" />
              <span class="menu-item-label">菜单管理</span>
            </div>
          </template>
          <el-menu-item index="/menu">菜品管理</el-menu-item>
          <el-menu-item index="/weekly-menu">本周菜单</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="showOwnerAdminMenus || showSystemAdminMenus" index="sub-system">
          <template #title>
            <div class="menu-item-inner">
              <Settings :size="18" stroke-width="2" />
              <span class="menu-item-label">系统管理</span>
            </div>
          </template>
          <el-menu-item v-if="showSystemAdminMenus" index="/system/tenants">租户管理</el-menu-item>
          <el-menu-item v-if="showOwnerAdminMenus" index="/store-config">门店配置</el-menu-item>
          <el-menu-item v-if="showOwnerAdminMenus" index="/system/membership-templates">会员卡管理</el-menu-item>
          <el-menu-item v-if="showOwnerAdminMenus" index="/system/retail-catalog">普通商品管理</el-menu-item>
        </el-sub-menu>
      </el-menu>

      <button
        type="button"
        class="sidebar-footer"
        :class="{ 'sidebar-footer--icon-only': sidebarCollapsed }"
        @click="handleAdminLogout"
      >
        <div v-show="!sidebarCollapsed" class="admin-info">
          <div class="avatar">{{ isDeliveryOnly ? '配送' : isSupportOnly ? '客服' : isSystemOnly ? '平台' : 'Admin' }}</div>
          <span>安全退出</span>
        </div>
        <LogOut :size="16" />
      </button>
    </aside>

    <main class="main-body">
      <div v-if="showSystemNotifications" class="admin-notifications-bar">
        <el-popover
          v-model:visible="notificationPopoverVisible"
          placement="bottom-end"
          :width="360"
          trigger="click"
          popper-class="admin-system-notifications-popover"
        >
          <template #reference>
            <button
              type="button"
              class="admin-notifications-bell"
              :class="{ 'admin-notifications-bell--active': hasUnread }"
              aria-label="系统消息"
            >
              <Bell :size="20" stroke-width="2" />
              <span
                v-if="hasUnread"
                class="admin-notifications-badge"
                aria-hidden="true"
              >{{ notificationBadgeText }}</span>
            </button>
          </template>

          <div class="admin-system-notifications-panel">
            <div class="admin-system-notifications-panel__head">
              <strong>系统消息</strong>
              <span v-if="hasUnread" class="admin-system-notifications-panel__count">
                {{ unacknowledgedCount }} 条待确认
              </span>
            </div>

            <div v-if="notificationsLoading && unreadItems.length === 0" class="admin-system-notifications-empty">
              加载中…
            </div>
            <div v-else-if="unreadItems.length === 0" class="admin-system-notifications-empty">
              暂无待确认消息
            </div>
            <ul v-else class="admin-system-notifications-list">
              <li
                v-for="item in unreadItems"
                :key="item.id"
                class="admin-system-notifications-item"
              >
                <p class="admin-system-notifications-item__title">{{ item.title }}</p>
                <p class="admin-system-notifications-item__message">{{ item.message }}</p>
                <div class="admin-system-notifications-item__actions">
                  <el-button
                    v-if="item.kind === 'sf_nightly_push' && !item.skip_reason"
                    size="small"
                    text
                    type="primary"
                    @click="goSfMonitor(item)"
                  >
                    查看详情
                  </el-button>
                  <el-button
                    size="small"
                    type="primary"
                    :loading="acknowledgingId === item.id"
                    @click="onAcknowledgeNotification(item)"
                  >
                    确认
                  </el-button>
                </div>
              </li>
            </ul>
          </div>
        </el-popover>
      </div>

      <header
        v-if="!hidePageTitle"
        class="top-header top-header--page-title-only"
        :class="{ 'top-header--delivery-toolbar': isDeliveryPage, 'top-header--with-bell': showSystemNotifications }"
      >
        <div class="page-heading">
          <h2 class="page-title">{{ pageTitle }}</h2>
          <p v-if="pageSubtitle" class="page-subtitle">{{ pageSubtitle }}</p>
        </div>
        <!-- v-show：Teleport 目标须在 DeliveryView 卸载前保留在 DOM；v-if 会先拆掉节点触发 Vue patch 异常（emitsOptions on null） -->
        <div
          v-show="isDeliveryPage"
          id="delivery-header-toolbar"
          class="page-header-toolbar"
          :aria-hidden="!isDeliveryPage"
          aria-label="配送大表筛选与操作"
        />
      </header>

      <nav
        v-if="openedTabs.length"
        class="admin-page-tabs"
        aria-label="已打开页面"
      >
        <div class="admin-page-tabs__scroll custom-scrollbar">
          <div
            v-for="tab in openedTabs"
            :key="tab.name"
            role="tab"
            tabindex="0"
            class="admin-page-tab"
            :class="{ 'admin-page-tab--active': activeTabName === tab.name }"
            :aria-selected="activeTabName === tab.name"
            @click="onTabClick(tab)"
            @keydown.enter="onTabClick(tab)"
          >
            <span class="admin-page-tab__label">{{ tab.title }}</span>
            <button
              v-if="openedTabs.length > 1"
              type="button"
              class="admin-page-tab__close"
              aria-label="关闭"
              @click.stop="onTabClose(tab)"
            >
              <X :size="14" stroke-width="2" />
            </button>
          </div>
        </div>
      </nav>

      <router-view v-slot="{ Component, route: viewRoute }">
        <keep-alive :include="keepAliveInclude" :max="ADMIN_TABS_MAX_CACHE">
          <component :is="Component" :key="viewRoute.name" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>
