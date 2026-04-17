<template>
  <view class="page">
    <OkNavbar title="" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle">
      <view class="dash-inner">
        <view v-if="!loading" class="dash-greet">
          <text class="dash-greet-line">
            你好，{{ displayName }}。今日待配送{{ pendingDeliveryCount }}单，已配送{{ deliveredCount }}单
          </text>
        </view>
        <view class="dash-header">
          <view class="dash-header-text">
            <text class="dash-title">今日配送单 👌</text>
            <text v-if="deliveryDate" class="dash-date">{{ deliveryDate }}</text>
            <text v-if="assignedLine" class="dash-areas">{{ assignedLine }}</text>
          </view>
          <text class="dash-count">共 {{ taskCount }} 笔</text>
        </view>

        <view v-if="loading" class="dash-state">加载中…</view>
        <view v-else-if="!taskCount" class="dash-state dash-state--muted">今日暂无待配送会员（或尚未分配片区）</view>

        <template v-else>
          <view v-for="g in groups" :key="g.area" class="area-block">
            <text class="area-heading">{{ g.area }}</text>
            <view
              v-for="t in g.items"
              :key="t.single_order_id ? 's-' + t.single_order_id : 'm-' + t.member_id"
              class="rider-task-card"
              :class="{ 'rider-task-card--done': t.is_delivered, 'rider-task-card--pending': !t.is_delivered }"
            >
              <view class="task-main">
                <view class="task-header">
                  <text class="task-name">{{ t.name || '会员' }}</text>
                  <view class="btn-call" role="button" @click="call(t.phone)">
                    <text class="btn-call-text">拨打电话</text>
                  </view>
                </view>
                <text class="task-phone">{{ t.phone }}</text>
                <text class="task-addr">{{ t.address }}</text>
                <text v-if="t.dish_title" class="task-remarks">单次点餐：{{ t.dish_title }}</text>
                <text v-if="t.remarks" class="task-remarks">备注：{{ t.remarks }}</text>
              </view>
              <view class="task-footer">
                <button
                  v-if="!t.is_delivered"
                  class="btn-confirm-delivery"
                  :disabled="confirmBusy(t)"
                  @click="onConfirm(t)"
                >
                  {{ confirmBusy(t) ? '提交中…' : '确认送达 OK' }}
                </button>
                <text v-else class="done-text">👌 已送达</text>
              </view>
            </view>
          </view>
        </template>

        <button class="btn-logout" @click="logout">退出登录</button>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getNavbarLayout } from '@/utils/navbar.js'
import { clearCourierToken, setAppUserMode, setCourierMeCache } from '@/utils/api.js'
import {
  confirmCourierDelivery,
  confirmSingleOrderDelivery,
  fetchCourierMe,
  fetchCourierTasks,
} from '@/utils/courierApi.js'
import { syncCustomTabBar, getCustomTabBarBottomReservePx } from '@/utils/customTabBar.js'

const loading = ref(true)
const profile = ref(null)
const groups = ref([])
const deliveryDate = ref('')
const assignedAreas = ref([])
/** 订阅任务为 member_id，单次订单为 single_order_id */
const confirmingId = ref(null)
const confirmingKind = ref('') // 'member' | 'single'

const scrollStyle = ref({})

const taskCount = computed(() =>
  groups.value.reduce((n, g) => n + (g.items?.length || 0), 0),
)

const displayName = computed(() => {
  const n = profile.value?.name?.trim()
  if (n) return n
  return '配送员'
})

const pendingDeliveryCount = computed(() => {
  let n = 0
  for (const g of groups.value) {
    for (const t of g.items || []) {
      if (!t.is_delivered) n++
    }
  }
  return n
})

const deliveredCount = computed(() => {
  let n = 0
  for (const g of groups.value) {
    for (const t of g.items || []) {
      if (t.is_delivered) n++
    }
  }
  return n
})

const assignedLine = computed(() => {
  const a = assignedAreas.value
  if (!a?.length) return ''
  return `负责片区：${a.join('、')}`
})

onShow(() => {
  syncCustomTabBar()
  const { navBarTotal } = getNavbarLayout()
  const bottom = getCustomTabBarBottomReservePx()
  scrollStyle.value = { height: `calc(100vh - ${navBarTotal + bottom}px)` }
  loadTasks()
})

async function loadTasks() {
  loading.value = true
  try {
    const [me, data] = await Promise.all([fetchCourierMe(), fetchCourierTasks()])
    setCourierMeCache(me)
    profile.value = me
    deliveryDate.value = data.delivery_date || ''
    assignedAreas.value = data.assigned_areas || []
    groups.value = data.groups || []
  } catch (e) {
    const status = e && typeof e === 'object' ? e.status : undefined
    if (status === 401) {
      clearCourierToken()
      uni.redirectTo({ url: '/pages/courier/login' })
      return
    }
    const msg = e instanceof Error ? e.message : '加载失败'
    profile.value = null
    groups.value = []
    setTimeout(() => {
      uni.showToast({ title: msg, icon: 'none' })
    }, 80)
  } finally {
    loading.value = false
  }
}

function call(phone) {
  if (!phone) return
  uni.makePhoneCall({ phoneNumber: String(phone) })
}

function confirmBusy(t) {
  if (!t || t.is_delivered) return false
  if (t.task_kind === 'single' && t.single_order_id) {
    return confirmingKind.value === 'single' && confirmingId.value === t.single_order_id
  }
  return confirmingKind.value === 'member' && confirmingId.value === t.member_id
}

async function onConfirm(t) {
  if (!t || t.is_delivered) return
  if (t.task_kind === 'single' && t.single_order_id) {
    confirmingKind.value = 'single'
    confirmingId.value = t.single_order_id
    try {
      await confirmSingleOrderDelivery(t.single_order_id)
      setTimeout(() => {
        uni.showToast({ title: '单次订单已送达', icon: 'success' })
      }, 50)
      await loadTasks()
    } catch (e) {
      const msg = e instanceof Error ? e.message : '操作失败'
      setTimeout(() => {
        uni.showToast({ title: msg, icon: 'none' })
      }, 80)
    } finally {
      confirmingId.value = null
      confirmingKind.value = ''
    }
    return
  }
  if (!t.member_id) return
  confirmingKind.value = 'member'
  confirmingId.value = t.member_id
  try {
    await confirmCourierDelivery(t.member_id, deliveryDate.value || undefined)
    setTimeout(() => {
      uni.showToast({ title: '已确认送达', icon: 'success' })
    }, 50)
    await loadTasks()
  } catch (e) {
    const msg = e instanceof Error ? e.message : '操作失败'
    setTimeout(() => {
      uni.showToast({ title: msg, icon: 'none' })
    }, 80)
  } finally {
    confirmingId.value = null
    confirmingKind.value = ''
  }
}

function logout() {
  clearCourierToken()
  setAppUserMode('member')
  uni.switchTab({ url: '/pages/order/index' })
}
</script>

<style lang="scss" scoped>
@use "sass:color" as color;

.page {
  background: $ok-slate-50;
  min-height: 100vh;
}

.scroll {
  box-sizing: border-box;
}

.dash-inner {
  padding: 40rpx;
  padding-bottom: 80rpx;
}

.dash-greet {
  margin-bottom: 28rpx;
}

.dash-greet-line {
  display: block;
  font-size: 30rpx;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.55;
}

.dash-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 30rpx;
  gap: 24rpx;
}

.dash-header-text {
  flex: 1;
  min-width: 0;
}

.dash-title {
  display: block;
  font-size: 44rpx;
  font-weight: 950;
  font-style: italic;
  color: $ok-rider-blue;
}

.dash-date {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  font-weight: 700;
  color: #64748b;
}

.dash-areas {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  font-weight: 700;
  color: #94a3b8;
  line-height: 1.4;
}

.dash-count {
  font-size: 24rpx;
  font-weight: 900;
  color: #999;
  flex-shrink: 0;
}

.dash-state {
  text-align: center;
  padding: 60rpx 20rpx;
  font-size: 28rpx;
  color: $ok-slate-600;
}

.dash-state--muted {
  color: #94a3b8;
}

.area-block {
  margin-bottom: 24rpx;
}

.area-heading {
  display: block;
  font-size: 26rpx;
  font-weight: 950;
  color: $ok-forest-green;
  margin-bottom: 16rpx;
  padding-left: 8rpx;
}

.rider-task-card {
  background: #fff;
  border-radius: 36rpx;
  border: 1rpx solid #e2e8f0;
  padding: 0;
  margin-bottom: 28rpx;
  box-shadow: 0 12rpx 40rpx rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.rider-task-card--pending {
  position: relative;
  border-color: #bfdbfe;
  box-shadow: 0 12rpx 36rpx rgba(37, 99, 235, 0.08);
}

.rider-task-card--pending::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 8rpx;
  background: $ok-rider-blue;
  border-radius: 36rpx 0 0 36rpx;
}

.rider-task-card--done {
  opacity: 0.62;
  border-style: dashed;
  border-color: #cbd5e1;
  box-shadow: none;
}

.task-main {
  padding: 36rpx 36rpx 28rpx;
}

.task-footer {
  padding: 0 36rpx 36rpx;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}

.task-name {
  font-size: 36rpx;
  font-weight: 950;
}

.task-phone {
  display: block;
  font-size: 26rpx;
  color: #64748b;
  font-weight: 700;
  margin-bottom: 16rpx;
}

.btn-call {
  flex-shrink: 0;
  background: #eff6ff;
  padding: 12rpx 26rpx;
  border-radius: 999rpx;
  border: 1rpx solid #dbeafe;
}

.btn-call-text {
  font-size: 24rpx;
  font-weight: 900;
  color: $ok-rider-blue;
}

.task-addr {
  font-size: 24rpx;
  color: #666;
  font-weight: 700;
  line-height: 1.5;
  margin-bottom: 16rpx;
}

.task-remarks {
  display: block;
  font-size: 22rpx;
  color: #94a3b8;
  margin-bottom: 0;
  line-height: 1.4;
}

.btn-confirm-delivery {
  width: 100%;
  background: linear-gradient(
    180deg,
    color.adjust($ok-rider-blue, $lightness: 4%) 0%,
    $ok-rider-blue 100%
  );
  color: #fff;
  padding: 28rpx;
  border-radius: 28rpx;
  font-weight: 950;
  border: none;
  font-size: 30rpx;
  margin-top: 8rpx;
  box-shadow: 0 8rpx 24rpx rgba(37, 99, 235, 0.25);
}

.btn-confirm-delivery[disabled] {
  opacity: 0.65;
}

.done-text {
  display: block;
  text-align: center;
  color: $ok-emerald;
  font-weight: 950;
  font-size: 28rpx;
  padding: 20rpx 0;
}

.btn-logout {
  background: none;
  border: none;
  color: #ccc;
  margin-top: 40rpx;
  font-weight: 950;
  font-size: 28rpx;
}
</style>
