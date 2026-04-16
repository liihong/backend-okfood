<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  Users,
  Truck,
  Utensils,
  BarChart3,
  MapPin,
  DollarSign,
  LogOut,
  Plus,
  X,
  Bike,
  ClipboardList,
} from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { useToast } from '../composables/useToast.js'

const route = useRoute()
const { showToast } = useToast()

const pageTitle = computed(() => route.meta.title || 'OK Fine Admin')

const navItems = [
  { name: 'dashboard', label: '营业概览', icon: BarChart3 },
  { name: 'users', label: '会员档案', icon: Users },
  { name: 'card-orders', label: '开卡工单', icon: ClipboardList },
  { name: 'delivery', label: '配送大表', icon: Truck },
  { name: 'regions', label: '配送区域', icon: MapPin },
  { name: 'couriers', label: '配送员', icon: Bike },
  { name: 'finance', label: '财务中心', icon: DollarSign },
  { name: 'menu', label: '菜品管理', icon: Utensils },
]

const showOrderModal = ref(false)
const regionOptionsForOrder = ref([{ value: '未分配', label: '未分配' }])

const newOrder = reactive({
  name: '',
  phone: '',
  address: '',
  plan: '周卡',
  area: '未分配',
})

async function fetchRegionOptionsForOrder() {
  if (!adminAccessToken.value) {
    regionOptionsForOrder.value = [{ value: '未分配', label: '未分配' }]
    return
  }
  try {
    const list = await apiJson('/api/admin/delivery-regions', {}, { auth: true })
    const active = (list || []).filter((r) => r.is_active !== false)
    const opts = active.map((r) => ({ value: r.name, label: r.name }))
    regionOptionsForOrder.value = opts.length ? opts : [{ value: '未分配', label: '未分配' }]
  } catch {
    regionOptionsForOrder.value = [{ value: '未分配', label: '未分配' }]
  }
}

const resetNewOrder = () => {
  newOrder.name = ''
  newOrder.phone = ''
  newOrder.address = ''
  newOrder.plan = '周卡'
  newOrder.area = regionOptionsForOrder.value[0]?.value || '未分配'
}

watch(showOrderModal, (open) => {
  if (open) void fetchRegionOptionsForOrder()
})

const handleFastOrder = () => {
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  showOrderModal.value = false
  resetNewOrder()
  showToast(
    '极速开单需后端提供管理员创建会员接口后对接；请使用会员端注册或其它录入流程',
    'error',
  )
}
</script>

<template>
  <div class="admin-layout">
    <aside class="sidebar">
      <div class="logo-area">
        <div class="logo-box">&#128076;</div>
        <div class="logo-text">
          <h1>OK Fine</h1>
          <span>SUPER ADMIN</span>
        </div>
      </div>

      <nav class="nav-list">
        <RouterLink
          v-for="item in navItems"
          :key="item.name"
          v-slot="{ navigate, isActive }"
          :to="{ name: item.name }"
          custom
        >
          <button type="button" :class="{ active: isActive }" @click="navigate">
            <component :is="item.icon" :size="18" />
            {{ item.label }}
          </button>
        </RouterLink>
      </nav>

      <button type="button" class="sidebar-footer" @click="handleAdminLogout">
        <div class="admin-info">
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
        <button type="button" class="btn-primary" @click="showOrderModal = true">
          <Plus :size="20" /> 极速开单
        </button>
      </header>

      <router-view />
    </main>

    <div v-if="showOrderModal" class="modal-overlay">
      <div class="modal-card">
        <div class="modal-header">
          <div class="header-info">
            <h3>极速开单 · OK Fine</h3>
            <p>MANUAL ORDER REGISTRATION</p>
          </div>
          <button type="button" class="close-btn" @click="showOrderModal = false">
            <X :size="20" />
          </button>
        </div>
        <form class="modal-form" @submit.prevent="handleFastOrder">
          <div class="form-row">
            <div class="form-group">
              <label>客户姓名</label>
              <input v-model="newOrder.name" required placeholder="如：张女士" />
            </div>
            <div class="form-group">
              <label>手机号码</label>
              <input v-model="newOrder.phone" required maxlength="11" placeholder="11位手机号" />
            </div>
          </div>
          <div class="form-group">
            <label>详细配送地址</label>
            <textarea v-model="newOrder.address" required rows="2" placeholder="详细楼号、房号..."></textarea>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>订阅套餐</label>
              <select v-model="newOrder.plan">
                <option value="次卡">次卡 (1次)</option>
                <option value="周卡">周卡 (6次)</option>
                <option value="月卡">月卡 (24次)</option>
              </select>
            </div>
            <div class="form-group">
              <label>所属区域</label>
              <select v-model="newOrder.area">
                <option v-for="o in regionOptionsForOrder" :key="o.value" :value="o.value">
                  {{ o.label }}
                </option>
              </select>
            </div>
          </div>
          <button type="submit" class="btn-submit-order">确认收款并开启计划 &#128076;</button>
        </form>
      </div>
    </div>
  </div>
</template>
