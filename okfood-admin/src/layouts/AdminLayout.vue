<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  Users,
  Truck,
  Utensils,
  BarChart3,
  MapPin,
  DollarSign,
  LogOut,
  ClipboardList,
  ChevronsLeft,
  ChevronsRight,
  Settings,
} from 'lucide-vue-next'
import { handleAdminLogout, adminKind, hydrateTokenFromStorage } from '../admin/core.js'

const SIDEBAR_COLLAPSED_KEY = 'okfood-admin-sidebar-collapsed'

const route = useRoute()

const isDeliveryOnly = computed(() => adminKind.value === 'delivery')
const isSupportOnly = computed(() => adminKind.value === 'support')
const isSystemOnly = computed(() => adminKind.value === 'system')

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
})

watch(sidebarCollapsedPref, (v) => {
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, v ? '1' : '0')
  } catch {
    /* 同上 */
  }
})
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
      <header v-if="!hidePageTitle" class="top-header top-header--page-title-only">
        <h2 class="page-title">{{ pageTitle }}</h2>
      </header>

      <router-view />
    </main>
  </div>
</template>
