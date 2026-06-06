<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Users,
  Utensils,
  BarChart3,
  MapPin,
  DollarSign,
  ClipboardList,
  Package,
  ChevronsLeft,
  ChevronsRight,
  Settings,
  X,
  Bell,
  Truck,
  CreditCard,
  UserCircle,
  Building2,
  Boxes,
  MapPinned,
  Activity,
  Megaphone,
  Tags,
} from 'lucide-vue-next'
import {
  handleAdminLogout,
  adminKind,
  adminAccessToken,
  hydrateTokenFromStorage,
  peekAdminJwtUsername,
} from '../admin/core.js'
import { useAdminTabsStore } from '../stores/adminTabs.js'
import {
  ADMIN_TABS_MAX_CACHE,
  ADMIN_DELIVERY_WORKBENCH_TRIAD,
} from '../constants/adminTabComponents.js'
import { useAdminSystemNotifications } from '../composables/useAdminSystemNotifications.js'
import { useShanghaiLiveClock } from '../composables/useShanghaiLiveClock.js'
import { useToast } from '../composables/useToast.js'
import { resolveNotificationDeliveryDate } from '../utils/systemNotificationNav.js'

/** 桌面侧栏收起状态本地持久化键 */
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
const { liveClockHm, liveClockDate } = useShanghaiLiveClock()

const notificationPopoverVisible = ref(false)

const isDeliveryOnly = computed(() => adminKind.value === 'delivery')
const isSupportOnly = computed(() => adminKind.value === 'support')
const isSystemOnly = computed(() => adminKind.value === 'system')

/** 店主、配送、客服账号展示系统消息铃铛（平台管理员除外） */
const showSystemNotifications = computed(() => !isSystemOnly.value)

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
  const d = resolveNotificationDeliveryDate(item)
  notificationPopoverVisible.value = false
  const query = d ? { delivery_date: d } : {}
  router.push({ path: '/delivery-sf-orders', query })
}

function goOrdersManage(item) {
  const d = resolveNotificationDeliveryDate(item)
  notificationPopoverVisible.value = false
  const query = d ? { delivery_date: d, tab: 'single' } : { tab: 'single' }
  router.push({ path: '/orders', query })
}

function parseCardOrderIdFromNotification(item) {
  const marker = String(item?.skip_reason || '').trim()
  const m1 = marker.match(/^card_order_id:(\d+)$/)
  if (m1) return Number(m1[1])
  const title = String(item?.title || '')
  const m2 = title.match(/工单#(\d+)/)
  if (m2) return Number(m2[1])
  return null
}

function goCardOrders(item) {
  notificationPopoverVisible.value = false
  const oid = parseCardOrderIdFromNotification(item)
  const query = oid ? { order_id: String(oid) } : {}
  router.push({ path: '/card-orders', query })
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

/** 配送大表：第二行挂载筛选工具条（Teleport 目标） */
const isDeliveryPage = computed(() => route.name === 'delivery')

/** 顶栏 Tab 左侧图标（与参考稿一致），未配置则仅占位留白由样式控制 */
const TAB_ROUTE_ICONS = {
  dashboard: BarChart3,
  users: Users,
  'card-orders': ClipboardList,
  orders: Package,
  delivery: Truck,
  regions: MapPin,
  'delivery-range-check': MapPinned,
  couriers: UserCircle,
  'delivery-sf-orders': Activity,
  finance: DollarSign,
  menu: Utensils,
  'weekly-menu': Utensils,
  'store-config': Settings,
  'system-tenants': Building2,
  'system-membership-templates': CreditCard,
  'system-dish-categories': Tags,
  'system-retail-catalog': Boxes,
  'marketing-coupon-templates': Megaphone,
  'marketing-member-coupons': Megaphone,
}

function tabLeadingIcon(routeName) {
  return TAB_ROUTE_ICONS[routeName] ?? null
}

const activeMenuPath = computed(() => route.path)

/** JWT sub：登录用户名；解码失败时再回落为角色占位名 */
const adminJwtLoginId = computed(() => peekAdminJwtUsername(adminAccessToken.value))

const adminNavbarDisplayName = computed(() => {
  const id = adminJwtLoginId.value
  if (id) return id
  if (isDeliveryOnly.value) return '配送工作台'
  if (isSupportOnly.value) return '客服工作台'
  if (isSystemOnly.value) return '平台管理'
  return '管理员'
})

/** 头像圈内短字：优先登录名首字，其次占位名首字 */
const adminNavbarAvatarChar = computed(() => {
  const id = adminJwtLoginId.value
  const fallback = adminNavbarDisplayName.value
  const src = id || fallback
  if (!src) return '?'
  const ch = src[0]
  return /[a-z]/i.test(ch) ? ch.toUpperCase() : ch
})

function onUserMenuCommand(command) {
  if (command === 'logout') {
    handleAdminLogout()
    return
  }
  if (command === 'password') {
    /** 修改密码：后续再接接口与安全流程 */
    showToast('修改密码功能开发中', 'info')
    return
  }
}
/** 桌面：侧栏收起偏好（持久化；Logo 旁双箭头按钮切换） */
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

/** 实际是否收起侧栏：窄屏用展开态；桌面来自用户偏好（与 localStorage 同步） */
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
    /** 与大表 / 片区并列：三联页任一进入即在顶栏补全另外两个（店主、客服工作台） */
    const n = typeof route.name === 'string' ? route.name : ''
    if (
      showFullAdminMenus.value &&
      n &&
      ADMIN_DELIVERY_WORKBENCH_TRIAD.includes(n)
    ) {
      tabsStore.ensureDeliveryWorkbenchTriad(router, n)
    }
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
        <div class="logo-box" aria-hidden="true">OK</div>
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
        popper-class="okfood-sidebar-menu-popup"
        background-color="transparent"
        text-color="rgba(255, 255, 255, 0.75)"
        active-text-color="#ffffff"
      >
        <el-menu-item v-if="showFullAdminMenus" index="/dashboard">
          <!-- 外层必须用 div：el-menu--collapse 会把 >span 设为 width:0 隐藏，连图标一起没了 -->
          <div class="menu-item-inner">
            <BarChart3 :size="20" stroke-width="2" />
            <span class="menu-item-label">营业概览</span>
          </div>
        </el-menu-item>
        <el-menu-item v-if="showFullAdminMenus" index="/users">
          <div class="menu-item-inner">
            <Users :size="20" stroke-width="2" />
            <span class="menu-item-label">会员档案</span>
          </div>
        </el-menu-item>
        <el-menu-item v-if="showFullAdminMenus" index="/card-orders">
          <div class="menu-item-inner">
            <ClipboardList :size="20" stroke-width="2" />
            <span class="menu-item-label">开卡工单</span>
          </div>
        </el-menu-item>
        <el-menu-item v-if="showFullAdminMenus" index="/orders">
          <div class="menu-item-inner">
            <Package :size="20" stroke-width="2" />
            <span class="menu-item-label">订单管理</span>
          </div>
        </el-menu-item>
        <el-sub-menu index="sub-delivery">
          <template #title>
            <div class="menu-item-inner">
              <MapPin :size="20" stroke-width="2" />
              <span class="menu-item-label">配送管理</span>
            </div>
          </template>
          <el-menu-item v-if="showFullAdminMenus" index="/delivery">配送大表</el-menu-item>
          <el-menu-item index="/delivery-range-check">配送资质检验</el-menu-item>
          <el-menu-item index="/delivery-sf-orders">顺丰订单监控</el-menu-item>
          <el-menu-item index="/regions">配送区域管理</el-menu-item>
          <el-menu-item index="/couriers">配送员管理</el-menu-item>
        </el-sub-menu>

        <el-menu-item v-if="showOwnerAdminMenus" index="/finance">
          <div class="menu-item-inner">
            <DollarSign :size="20" stroke-width="2" />
            <span class="menu-item-label">财务中心</span>
          </div>
        </el-menu-item>

        <el-sub-menu v-if="showFullAdminMenus" index="sub-menu-mgmt">
          <template #title>
            <div class="menu-item-inner">
              <Utensils :size="20" stroke-width="2" />
              <span class="menu-item-label">菜单管理</span>
            </div>
          </template>
          <el-menu-item index="/menu">菜品管理</el-menu-item>
          <el-menu-item index="/weekly-menu">本周菜单</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="showFullAdminMenus" index="sub-marketing">
          <template #title>
            <div class="menu-item-inner">
              <Megaphone :size="20" stroke-width="2" />
              <span class="menu-item-label">小程序营销</span>
            </div>
          </template>
          <el-menu-item index="/marketing/coupon-templates">优惠券管理</el-menu-item>
          <el-menu-item index="/marketing/member-coupons">优惠券发放</el-menu-item>
          <el-menu-item index="/marketing/douyin-products">抖音商品设置</el-menu-item>
          <el-menu-item index="/marketing/douyin-redemptions">核销记录查询</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="showOwnerAdminMenus || showSystemAdminMenus" index="sub-system">
          <template #title>
            <div class="menu-item-inner">
              <Settings :size="20" stroke-width="2" />
              <span class="menu-item-label">系统管理</span>
            </div>
          </template>
          <el-menu-item v-if="showSystemAdminMenus" index="/system/tenants">租户管理</el-menu-item>
          <el-menu-item v-if="showOwnerAdminMenus" index="/store-config">门店配置</el-menu-item>
          <el-menu-item v-if="showOwnerAdminMenus" index="/system/membership-templates">会员卡管理</el-menu-item>
          <el-menu-item v-if="showOwnerAdminMenus" index="/system/dish-categories">菜品分类</el-menu-item>
          <el-menu-item v-if="showOwnerAdminMenus" index="/system/retail-catalog">普通商品管理</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </aside>

    <main class="main-body">
      <!-- 顶栏标签 + 右侧系统消息铃铛（参考稿 top-tab-scroller） -->
      <div v-if="openedTabs.length" class="admin-top-tab-bar">
        <nav class="admin-page-tabs" aria-label="已打开页面">
          <div class="admin-page-tabs__scroll custom-scrollbar admin-page-tabs__scroll--top-bar">
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
              <component
                :is="tabLeadingIcon(tab.name)"
                v-if="tabLeadingIcon(tab.name)"
                class="admin-page-tab__icon"
                :size="16"
                stroke-width="2.25"
              />
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

        <div class="admin-top-tab-bar__trailing">
          <el-popover
            v-if="showSystemNotifications"
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
                      class="admin-notifications-action-btn admin-notifications-action-btn--secondary"
                      @click="goSfMonitor(item)"
                    >
                      查看详情
                    </el-button>
                    <el-button
                      v-if="item.kind === 'single_meal_order_paid'"
                      size="small"
                      class="admin-notifications-action-btn admin-notifications-action-btn--secondary"
                      @click="goOrdersManage(item)"
                    >
                      去订单管理
                    </el-button>
                    <el-button
                      v-if="item.kind === 'miniprogram_card_order_pending'"
                      size="small"
                      class="admin-notifications-action-btn admin-notifications-action-btn--secondary"
                      @click="goCardOrders(item)"
                    >
                      去开卡工单审批
                    </el-button>
                    <el-button
                      size="small"
                      class="admin-notifications-action-btn admin-notifications-action-btn--primary"
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

          <div class="admin-header-live-clock" aria-live="polite">
            <span class="admin-header-live-clock__hm">{{ liveClockHm }}</span>
            <span class="admin-header-live-clock__date">{{ liveClockDate }}</span>
          </div>

          <el-dropdown trigger="click" placement="bottom-end" @command="onUserMenuCommand">
            <button type="button" class="admin-user-menu-trigger" aria-haspopup="menu" aria-label="账户菜单">
              <span class="admin-user-avatar" aria-hidden="true">{{ adminNavbarAvatarChar }}</span>
              <span class="admin-user-name">{{ adminNavbarDisplayName }}</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- Teleport：须始终在 DOM（v-show）；与顶栏分离后单独成行 -->
      <div
        v-show="isDeliveryPage"
        id="delivery-header-toolbar"
        class="admin-delivery-toolbar-host"
        :aria-hidden="!isDeliveryPage"
        aria-label="配送大表筛选与操作"
      />

      <div class="main-body__router-host">
        <router-view v-slot="{ Component, route: viewRoute }">
          <keep-alive :include="keepAliveInclude" :max="ADMIN_TABS_MAX_CACHE">
            <component :is="Component" :key="viewRoute.name" />
          </keep-alive>
        </router-view>
      </div>
    </main>
  </div>
</template>
