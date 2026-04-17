<template>
  <view class="page">
    <OkNavbar title="个人中心" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle">
      <view class="inner">
        <view class="head-card">
          <text class="head-icon">🛵</text>
          <view class="head-text">
            <text class="head-name">{{ displayName }}</text>
            <text class="head-phone">{{ profile?.phone_masked || '—' }}</text>
            <text v-if="assignedLine" class="head-areas">{{ assignedLine }}</text>
          </view>
        </view>

        <view class="card">
          <text class="card-title">配送费</text>
          <view class="fee-grid">
            <view class="fee-cell">
              <text class="fee-label">待结算</text>
              <text class="fee-val fee-val--pending">¥ {{ profile?.fee_pending ?? '0.00' }}</text>
            </view>
            <view class="fee-cell">
              <text class="fee-label">已结算累计</text>
              <text class="fee-val">¥ {{ profile?.fee_settled ?? '0.00' }}</text>
            </view>
          </view>
        </view>

        <view class="list">
          <view class="row" @click="goHome">
            <text class="row-label">配送员首页</text>
            <text class="row-arrow">›</text>
          </view>
          <view class="row" @click="goDashboard">
            <text class="row-label">今日配送单</text>
            <text class="row-arrow">›</text>
          </view>
          <view class="row row--muted" @click="goCustomer">
            <text class="row-label">返回会员点餐</text>
            <text class="row-arrow">›</text>
          </view>
        </view>

        <button class="btn-out" @click="logout">退出配送员登录</button>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getNavbarLayout } from '@/utils/navbar.js'
import {
  getCourierToken,
  clearCourierToken,
  setAppUserMode,
  setCourierMeCache,
} from '@/utils/api.js'
import { fetchCourierMe } from '@/utils/courierApi.js'
import { syncCustomTabBar, getCustomTabBarBottomReservePx } from '@/utils/customTabBar.js'

const profile = ref(null)
const scrollStyle = ref({})

const displayName = computed(() => {
  const n = profile.value?.name?.trim()
  if (n) return n
  return '配送员'
})

const assignedLine = computed(() => {
  const a = profile.value?.assigned_areas
  if (!a?.length) return ''
  return `负责片区：${a.join('、')}`
})

onShow(() => {
  syncCustomTabBar()
  const { navBarTotal } = getNavbarLayout()
  const bottom = getCustomTabBarBottomReservePx()
  scrollStyle.value = { height: `calc(100vh - ${navBarTotal + bottom}px)` }
  void loadProfile()
})

async function loadProfile() {
  if (!getCourierToken()) {
    uni.redirectTo({ url: '/pages/courier/login' })
    return
  }
  try {
    const me = await fetchCourierMe()
    setCourierMeCache(me)
    profile.value = me
  } catch (e) {
    const status = e && typeof e === 'object' ? e.status : undefined
    if (status === 401) {
      clearCourierToken()
      uni.redirectTo({ url: '/pages/courier/login' })
      return
    }
    const msg = e instanceof Error ? e.message : '加载失败'
    uni.showToast({ title: msg, icon: 'none' })
  }
}

function goHome() {
  uni.navigateTo({ url: '/pages/courier/home' })
}

function goDashboard() {
  uni.switchTab({ url: '/pages/courier/dashboard' })
}

function goCustomer() {
  setAppUserMode('member')
  uni.switchTab({ url: '/pages/order/index' })
}

function logout() {
  clearCourierToken()
  setAppUserMode('member')
  uni.switchTab({ url: '/pages/order/index' })
}
</script>

<style lang="scss" scoped>
.page {
  background: #f8fafc;
  min-height: 100vh;
}

.scroll {
  box-sizing: border-box;
}

.inner {
  padding: 32rpx 40rpx calc(40rpx + env(safe-area-inset-bottom));
}

.head-card {
  display: flex;
  gap: 28rpx;
  align-items: flex-start;
  background: #fff;
  border-radius: 40rpx;
  padding: 36rpx;
  margin-bottom: 28rpx;
  border: 1px solid #e2e8f0;
}

.head-icon {
  font-size: 72rpx;
  line-height: 1;
}

.head-text {
  flex: 1;
  min-width: 0;
}

.head-name {
  display: block;
  font-size: 36rpx;
  font-weight: 950;
  color: #0f172a;
}

.head-phone {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  font-weight: 800;
  color: #64748b;
}

.head-areas {
  display: block;
  margin-top: 16rpx;
  font-size: 22rpx;
  font-weight: 700;
  color: #94a3b8;
  line-height: 1.45;
}

.card {
  background: #fff;
  border-radius: 40rpx;
  padding: 36rpx;
  margin-bottom: 28rpx;
  border: 1px solid #e2e8f0;
}

.card-title {
  display: block;
  font-size: 26rpx;
  font-weight: 950;
  color: $ok-forest-green;
  margin-bottom: 24rpx;
}

.fee-grid {
  display: flex;
  gap: 24rpx;
}

.fee-cell {
  flex: 1;
  background: #f8fafc;
  border-radius: 24rpx;
  padding: 28rpx 20rpx;
}

.fee-label {
  display: block;
  font-size: 22rpx;
  font-weight: 800;
  color: #64748b;
}

.fee-val {
  display: block;
  margin-top: 12rpx;
  font-size: 34rpx;
  font-weight: 950;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}

.fee-val--pending {
  color: $ok-rider-blue;
}

.list {
  background: #fff;
  border-radius: 40rpx;
  border: 1px solid #e2e8f0;
  overflow: hidden;
  margin-bottom: 36rpx;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 36rpx 32rpx;
  border-bottom: 1px solid #f1f5f9;
}

.row:last-child {
  border-bottom: none;
}

.row--muted {
  opacity: 0.75;
}

.row-label {
  font-size: 30rpx;
  font-weight: 900;
  color: #334155;
}

.row-arrow {
  font-size: 40rpx;
  color: #cbd5e1;
  font-weight: 300;
}

.btn-out {
  width: 100%;
  background: transparent;
  border: 2rpx solid #e2e8f0;
  color: #94a3b8;
  padding: 28rpx;
  border-radius: 28rpx;
  font-weight: 950;
  font-size: 28rpx;
}
</style>
