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
} from 'lucide-vue-next'
import { handleAdminLogout } from '../admin/core.js'

const SIDEBAR_COLLAPSED_KEY = 'okfood-admin-sidebar-collapsed'

const route = useRoute()

const pageTitle = computed(() => route.meta.title || 'OK Fine Admin')

const activeMenuPath = computed(() => route.path)

/** 用户选择的收起状态（窄屏下不生效，避免与移动端横向菜单冲突） */
const sidebarCollapsedPref = ref(false)

const isNarrowScreen = ref(false)

let sidebarMediaQuery = null

function syncNarrowScreen() {
  if (!sidebarMediaQuery) return
  isNarrowScreen.value = sidebarMediaQuery.matches
}

/** 实际是否收起侧栏（桌面有效） */
const sidebarCollapsed = computed(
  () => sidebarCollapsedPref.value && !isNarrowScreen.value,
)

function toggleSidebar() {
  sidebarCollapsedPref.value = !sidebarCollapsedPref.value
}

onMounted(() => {
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
          <span>SUPER ADMIN</span>
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
        class="sidebar-menu"
        :default-active="activeMenuPath"
        :collapse="sidebarCollapsed"
        router
        :ellipsis="false"
        background-color="transparent"
        text-color="rgba(255, 255, 255, 0.72)"
        active-text-color="#facc15"
      >
        <el-menu-item index="/dashboard">
          <!-- 外层必须用 div：el-menu--collapse 会把 >span 设为 width:0 隐藏，连图标一起没了 -->
          <div class="menu-item-inner">
            <BarChart3 :size="18" stroke-width="2" />
            <span class="menu-item-label">营业概览</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/users">
          <div class="menu-item-inner">
            <Users :size="18" stroke-width="2" />
            <span class="menu-item-label">会员档案</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/card-orders">
          <div class="menu-item-inner">
            <ClipboardList :size="18" stroke-width="2" />
            <span class="menu-item-label">开卡工单</span>
          </div>
        </el-menu-item>
        <el-menu-item index="/delivery">
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
        </el-sub-menu>

        <el-menu-item index="/finance">
          <div class="menu-item-inner">
            <DollarSign :size="18" stroke-width="2" />
            <span class="menu-item-label">财务中心</span>
          </div>
        </el-menu-item>

        <el-sub-menu index="sub-menu-mgmt">
          <template #title>
            <div class="menu-item-inner">
              <Utensils :size="18" stroke-width="2" />
              <span class="menu-item-label">菜单管理</span>
            </div>
          </template>
          <el-menu-item index="/menu">菜品管理</el-menu-item>
          <el-menu-item index="/weekly-menu">本周菜单</el-menu-item>
        </el-sub-menu>
      </el-menu>

      <button
        type="button"
        class="sidebar-footer"
        :class="{ 'sidebar-footer--icon-only': sidebarCollapsed }"
        @click="handleAdminLogout"
      >
        <div v-show="!sidebarCollapsed" class="admin-info">
          <div class="avatar">Admin</div>
          <span>安全退出</span>
        </div>
        <LogOut :size="16" />
      </button>
    </aside>

    <main class="main-body">
      <header class="top-header">
        <div class="title-wrap">
          <div class="live-indicator">
            <span class="dot"></span> System Live · New Xiang
          </div>
          <h2 class="page-title">{{ pageTitle }}</h2>
        </div>
      </header>

      <router-view />
    </main>
  </div>
</template>
