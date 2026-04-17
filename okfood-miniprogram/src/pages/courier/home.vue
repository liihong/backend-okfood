<template>
  <view v-if="authed" class="page">
    <OkNavbar title="" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle">
      <view class="inner">
        <view class="hero">
          <text class="hero-emoji">🛵</text>
          <text class="hero-title">配送员首页</text>
          <text v-if="profile?.name" class="hero-sub">你好，{{ profile.name }}</text>
          <text v-else class="hero-sub">今日加油👌</text>
        </view>

        <view class="card card--money">
          <text class="card-label">待结算配送费</text>
          <text class="card-money">¥ {{ feePending }}</text>
          <view class="card-row">
            <text class="card-muted">已结算累计 ¥ {{ feeSettled }}</text>
          </view>
        </view>

        <view class="card">
          <view class="card-head">
            <text class="card-h">今日订单</text>
            <text v-if="deliveryDate" class="card-date">{{ deliveryDate }}</text>
          </view>
          <view v-if="loading" class="state">加载中…</view>
          <template v-else>
            <view class="stat-row">
              <view class="stat-pill">
                <text class="stat-num">{{ pendingCount }}</text>
                <text class="stat-txt">待送达</text>
              </view>
              <view class="stat-pill stat-pill--dim">
                <text class="stat-num">{{ totalCount }}</text>
                <text class="stat-txt">今日共</text>
              </view>
            </view>
            <text v-if="assignedLine" class="areas">{{ assignedLine }}</text>
          </template>
          <button class="btn-primary" @click="goDashboard">查看今日配送单</button>
          <button class="btn-ghost" @click="goProfile">个人中心</button>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getNavbarLayout } from '@/utils/navbar.js'
import { getCourierToken, clearCourierToken, setCourierMeCache } from '@/utils/api.js'
import { fetchCourierMe, fetchCourierTasks } from '@/utils/courierApi.js'
import { syncCustomTabBar } from '@/utils/customTabBar.js'

const authed = ref(false)
const loading = ref(true)
const profile = ref(null)
const groups = ref([])
const deliveryDate = ref('')
const assignedAreas = ref([])
const scrollStyle = ref({})

const feePending = computed(() => profile.value?.fee_pending ?? '0.00')
const feeSettled = computed(() => profile.value?.fee_settled ?? '0.00')

const assignedLine = computed(() => {
  const a = assignedAreas.value
  if (!a?.length) return ''
  return `负责片区：${a.join('、')}`
})

const totalCount = computed(() =>
  groups.value.reduce((n, g) => n + (g.items?.length || 0), 0),
)

const pendingCount = computed(() => {
  let n = 0
  for (const g of groups.value) {
    for (const t of g.items || []) {
      if (!t.is_delivered) n++
    }
  }
  return n
})

onShow(() => {
  syncCustomTabBar()
  authed.value = false
  if (!getCourierToken()) {
    uni.redirectTo({ url: '/pages/courier/login' })
    return
  }
  authed.value = true
  const { navBarTotal } = getNavbarLayout()
  scrollStyle.value = { height: `calc(100vh - ${navBarTotal}px)` }
  void loadPage()
})

async function loadPage() {
  if (!getCourierToken()) {
    uni.redirectTo({ url: '/pages/courier/login' })
    return
  }
  loading.value = true
  try {
    const [me, tasks] = await Promise.all([fetchCourierMe(), fetchCourierTasks()])
    setCourierMeCache(me)
    profile.value = me
    deliveryDate.value = tasks.delivery_date || ''
    assignedAreas.value = tasks.assigned_areas || []
    groups.value = tasks.groups || []
  } catch (e) {
    const status = e && typeof e === 'object' ? e.status : undefined
    if (status === 401) {
      clearCourierToken()
      uni.redirectTo({ url: '/pages/courier/login' })
      return
    }
    const msg = e instanceof Error ? e.message : '加载失败'
    setTimeout(() => {
      uni.showToast({ title: msg, icon: 'none' })
    }, 80)
    profile.value = null
    groups.value = []
  } finally {
    loading.value = false
  }
}

function goDashboard() {
  uni.switchTab({ url: '/pages/courier/dashboard' })
}

function goProfile() {
  uni.switchTab({ url: '/pages/courier/profile' })
}
</script>

<style lang="scss" scoped>
.page {
  background: #fff;
  min-height: 100vh;
}

.scroll {
  box-sizing: border-box;
}

.inner {
  padding: 32rpx 40rpx 80rpx;
}

.hero {
  margin-bottom: 36rpx;
}

.hero-emoji {
  font-size: 72rpx;
  display: block;
  margin-bottom: 16rpx;
}

.hero-title {
  display: block;
  font-size: 44rpx;
  font-weight: 950;
  font-style: italic;
  color: $ok-rider-blue;
}

.hero-sub {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  font-weight: 700;
  color: #64748b;
}

.card {
  background: #fff;
  border-radius: 40rpx;
  border: 1px solid #eee;
  padding: 36rpx;
  margin-bottom: 28rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
}

.card--money {
  background: linear-gradient(135deg, #eff6ff 0%, #fff 48%);
  border-color: #dbeafe;
}

.card-label {
  display: block;
  font-size: 24rpx;
  font-weight: 800;
  color: #64748b;
}

.card-money {
  display: block;
  margin-top: 12rpx;
  font-size: 56rpx;
  font-weight: 950;
  color: $ok-rider-blue;
  font-variant-numeric: tabular-nums;
}

.card-row {
  margin-top: 16rpx;
}

.card-muted {
  font-size: 22rpx;
  font-weight: 700;
  color: #94a3b8;
}

.card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.card-h {
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-forest-green;
}

.card-date {
  font-size: 22rpx;
  font-weight: 700;
  color: #94a3b8;
}

.state {
  text-align: center;
  padding: 24rpx;
  color: #64748b;
  font-size: 28rpx;
}

.stat-row {
  display: flex;
  gap: 20rpx;
  margin-bottom: 20rpx;
}

.stat-pill {
  flex: 1;
  background: #f8fafc;
  border-radius: 24rpx;
  padding: 28rpx 20rpx;
  text-align: center;
}

.stat-pill--dim {
  opacity: 0.85;
}

.stat-num {
  display: block;
  font-size: 48rpx;
  font-weight: 950;
  color: $ok-rider-blue;
  font-variant-numeric: tabular-nums;
}

.stat-txt {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  font-weight: 800;
  color: #64748b;
}

.areas {
  display: block;
  font-size: 22rpx;
  font-weight: 700;
  color: #94a3b8;
  line-height: 1.45;
  margin-bottom: 28rpx;
}

.btn-primary {
  width: 100%;
  background: $ok-rider-blue;
  color: #fff;
  padding: 28rpx;
  border-radius: 28rpx;
  font-weight: 950;
  border: none;
  font-size: 30rpx;
  margin-bottom: 20rpx;
}

.btn-ghost {
  width: 100%;
  background: #f1f5f9;
  color: $ok-slate-600;
  padding: 28rpx;
  border-radius: 28rpx;
  font-weight: 900;
  border: none;
  font-size: 28rpx;
}
</style>
