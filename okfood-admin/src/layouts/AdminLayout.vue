<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
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

const activeMenuPath = computed(() => route.path)

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

      <el-menu
        class="sidebar-menu"
        :default-active="activeMenuPath"
        router
        :ellipsis="false"
        background-color="transparent"
        text-color="rgba(255, 255, 255, 0.72)"
        active-text-color="#facc15"
      >
        <el-menu-item index="/dashboard">
          <span class="menu-item-inner">
            <BarChart3 :size="18" stroke-width="2" />
            <span>营业概览</span>
          </span>
        </el-menu-item>
        <el-menu-item index="/users">
          <span class="menu-item-inner">
            <Users :size="18" stroke-width="2" />
            <span>会员档案</span>
          </span>
        </el-menu-item>
        <el-menu-item index="/card-orders">
          <span class="menu-item-inner">
            <ClipboardList :size="18" stroke-width="2" />
            <span>开卡工单</span>
          </span>
        </el-menu-item>
        <el-menu-item index="/delivery">
          <span class="menu-item-inner">
            <Truck :size="18" stroke-width="2" />
            <span>配送大表</span>
          </span>
        </el-menu-item>

        <el-sub-menu index="sub-delivery">
          <template #title>
            <span class="menu-item-inner">
              <MapPin :size="18" stroke-width="2" />
              <span>配送管理</span>
            </span>
          </template>
          <el-menu-item index="/regions">配送区域管理</el-menu-item>
          <el-menu-item index="/couriers">配送员管理</el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/finance">
          <span class="menu-item-inner">
            <DollarSign :size="18" stroke-width="2" />
            <span>财务中心</span>
          </span>
        </el-menu-item>

        <el-sub-menu index="sub-menu-mgmt">
          <template #title>
            <span class="menu-item-inner">
              <Utensils :size="18" stroke-width="2" />
              <span>菜单管理</span>
            </span>
          </template>
          <el-menu-item index="/menu">菜品管理</el-menu-item>
          <el-menu-item index="/weekly-menu">本周菜单</el-menu-item>
        </el-sub-menu>
      </el-menu>

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
