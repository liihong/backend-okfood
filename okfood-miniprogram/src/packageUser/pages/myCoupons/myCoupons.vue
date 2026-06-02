<template>
  <view class="page">
    <OkNavbar show-back title="我的优惠券" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="wrap">
        <view class="tabs">
          <text
            v-for="t in tabs"
            :key="t.key"
            class="tab"
            :class="{ 'tab--on': activeTab === t.key }"
            @tap="switchTab(t.key)"
          >{{ t.label }}</text>
        </view>

        <view v-if="loading" class="state">加载中…</view>
        <view v-else-if="!items.length" class="state">暂无优惠券</view>
        <view v-else class="list">
          <MemberCouponCard
            v-for="c in items"
            :key="c.id"
            :coupon="c"
            :disabled="c.status !== 'available'"
            compact
          />
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import MemberCouponCard from '@/components/MemberCouponCard/MemberCouponCard.vue'
import { getNavbarLayout } from '@/utils/navbar.js'
import { getMemberToken, clearMemberSession } from '@/utils/api.js'
import { listMemberCouponsWallet } from '@/utils/memberCouponWalletApi.js'

const scrollStyle = ref({})
const loading = ref(true)
const items = ref([])
const activeTab = ref('available')

const tabs = [
  { key: 'available', label: '可用' },
  { key: 'used', label: '已用' },
  { key: 'expired', label: '已过期' },
]

async function loadList() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const data = await listMemberCouponsWallet({ status: activeTab.value })
    items.value = Array.isArray(data) ? data : []
  } catch (e) {
    const msg = e instanceof Error ? e.message : '加载失败'
    uni.showToast({ title: msg, icon: 'none' })
    items.value = []
  } finally {
    loading.value = false
  }
}

function switchTab(key) {
  if (activeTab.value === key) return
  activeTab.value = key
  void loadList()
}

onShow(() => {
  const layout = getNavbarLayout()
  scrollStyle.value = { height: layout.scrollHeightPx }
  if (!getMemberToken()) {
    clearMemberSession()
    uni.reLaunch({ url: '/pages/mine/index' })
    return
  }
  void loadList()
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f8fafc;
}
.scroll {
  box-sizing: border-box;
}
.wrap {
  padding: 24rpx 28rpx 48rpx;
}
.tabs {
  display: flex;
  gap: 16rpx;
  margin-bottom: 24rpx;
}
.tab {
  padding: 12rpx 28rpx;
  border-radius: 999rpx;
  background: #fff;
  color: #64748b;
  font-size: 26rpx;
}
.tab--on {
  background: #0e5a44;
  color: #fff;
}
.state {
  text-align: center;
  color: #94a3b8;
  padding: 80rpx 0;
  font-size: 28rpx;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
</style>
