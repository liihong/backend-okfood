<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { UserMinus, Utensils, MapPin, ChevronRight } from 'lucide-vue-next'
import { apiJson, adminAccessToken, memberList, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const router = useRouter()

const stats = ref([])
const dashboardStatsLoading = ref(false)
const dishList = ref([])

async function fetchDashboardSummary() {
  if (!adminAccessToken.value) return
  dashboardStatsLoading.value = true
  try {
    const d = await apiJson('/api/admin/dashboard-summary', {}, { auth: true })
    const tl = Number(d?.today_leave_members) || 0
    const tp = Number(d?.today_meals_to_prepare) || 0
    const nl = Number(d?.tomorrow_leave_members) || 0
    const np = Number(d?.tomorrow_meals_to_prepare) || 0
    stats.value = [
      {
        label: '今日请假会员',
        value: tl,
        unit: '个',
        icon: UserMinus,
        bg: '#ffe4e6',
        color: '#e11d48',
      },
      {
        label: '今日需准备餐品',
        value: tp,
        unit: '个',
        icon: Utensils,
        bg: '#d1fae5',
        color: '#059669',
      },
      {
        label: '明日请假会员',
        value: nl,
        unit: '个',
        icon: UserMinus,
        bg: '#ffedd5',
        color: '#ea580c',
      },
      {
        label: '明日需准备餐品',
        value: np,
        unit: '个',
        icon: Utensils,
        bg: '#e0f2fe',
        color: '#0284c7',
      },
    ]
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    stats.value = []
    showToast(e instanceof Error ? e.message : '加载营业概览失败', 'error')
  } finally {
    dashboardStatsLoading.value = false
  }
}

async function fetchDishes() {
  if (!adminAccessToken.value) return
  try {
    const data = await apiJson('/api/admin/dishes', {}, { auth: true })
    dishList.value = Array.isArray(data) ? data : []
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    dishList.value = []
  }
}

onMounted(() => {
  void fetchDashboardSummary()
  void fetchDishes()
})
</script>

<template>
  <section class="tab-content animate-up">
    <p v-if="dashboardStatsLoading" class="members-loading">正在加载营业概览…</p>
    <p v-else-if="!stats.length" class="members-loading">暂无概览数据，请稍后重试或重新登录。</p>
    <div v-else class="stats-grid">
      <div v-for="(s, i) in stats" :key="i" class="stat-card">
        <div class="stat-icon" :style="{ backgroundColor: s.bg, color: s.color }">
          <component :is="s.icon" :size="20" />
        </div>
        <div class="stat-info">
          <p class="stat-label">{{ s.label }}</p>
          <div class="stat-value">
            {{ s.value }}<small>{{ s.unit }}</small>
          </div>
        </div>
      </div>
    </div>

    <div class="dashboard-row">
      <div class="delivery-preview">
        <div class="row-header">
          <h3>实时配餐流</h3>
          <button type="button" class="link-btn" @click="router.push({ name: 'delivery' })">
            查看配送大表 <ChevronRight :size="14" />
          </button>
        </div>
        <div class="task-mini-list">
          <p v-if="!memberList.length" class="members-loading">
            暂无会员列表数据；进入「会员档案」加载后将显示此处预览。
          </p>
          <div v-for="m in memberList.slice(0, 3)" :key="m.id" class="task-mini-item">
            <div class="task-user">
              <div class="id-tag">#0{{ m.id }}</div>
              <div class="user-info">
                <p class="u-name">{{ m.name }}</p>
                <p class="u-addr"><MapPin :size="10" />{{ m.address }}</p>
              </div>
            </div>
            <span class="status-tag">待派送</span>
          </div>
        </div>
      </div>

      <div class="sync-card">
        <div class="sync-content">
          <h3>菜品库</h3>
          <p class="sync-subtitle">DISH CATALOG</p>
          <div class="sync-box">
            <p class="sync-label">当前菜品数：</p>
            <p class="sync-dish">
              {{ dishList.length ? '共 ' + dishList.length + ' 道' : '暂无，请在菜品管理中录入' }}
            </p>
          </div>
        </div>
        <button type="button" class="btn-accent" @click="router.push({ name: 'menu' })">
          进入菜品管理
        </button>
      </div>
    </div>
  </section>
</template>
