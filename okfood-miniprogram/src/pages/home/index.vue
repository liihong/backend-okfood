<template>
  <view class="page" :style="pageStyle">
    <scroll-view
      scroll-y
      class="scroll"
      :style="scrollStyle"
      :show-scrollbar="false"
      refresher-enabled
      :refresher-triggered="refresherTriggered"
      @refresherrefresh="onRefresherRefresh"
    >
      <view class="home-page">
        <HomeBannerSwiper :banners="banners" :today-ymd="todayYmd" />
        <MemberLoginPromptBar @logged-in="onLoggedIn" />
        <HomeFeaturedSection :dish="todayDish" :loading="loading" @tap="goDetail" />
      </view>
    </scroll-view>
    <MemberCouponReminderHost v-if="couponHostReady" />
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { onShow, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import HomeBannerSwiper from '@/components/HomeBannerSwiper/HomeBannerSwiper.vue'
import MemberLoginPromptBar from '@/components/MemberLoginPromptBar/MemberLoginPromptBar.vue'
import HomeFeaturedSection from '@/components/HomeFeaturedSection/HomeFeaturedSection.vue'
import MemberCouponReminderHost from '@/components/MemberCouponReminderHost/MemberCouponReminderHost.vue'
import { fetchHomeBanners } from '@/utils/homeApi.js'
import { fetchTodayMenu, ymdTodayShanghai } from '@/utils/menuApi.js'
import { getTabPageLayoutStyles } from '@/utils/tabPageLayout.js'
import { syncCustomTabBar } from '@/utils/customTabBar.js'
import { reLaunchIfCourierModePreferred } from '@/utils/api.js'
import { requestDeliverySubscribeOncePerDay } from '@/utils/subscribeMsg.js'

const couponHostReady = ref(false)
const pageStyle = ref({})
const scrollStyle = ref({})
const loading = ref(true)
const refresherTriggered = ref(false)
const banners = ref([])
const todayDish = ref(null)
const todayYmd = ref(ymdTodayShanghai())
let loadSeq = 0

function syncTabLayout() {
  const { pageStyle: p, scrollStyle: s } = getTabPageLayoutStyles({ fullBleed: true })
  pageStyle.value = p
  scrollStyle.value = s
}

async function loadHomeData() {
  const seq = ++loadSeq
  todayYmd.value = ymdTodayShanghai()
  loading.value = true
  try {
    const [bannerList, dish] = await Promise.all([
      fetchHomeBanners().catch(() => []),
      fetchTodayMenu().catch(() => null),
    ])
    if (seq !== loadSeq) return
    banners.value = bannerList
    todayDish.value = dish
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

async function onRefresherRefresh() {
  refresherTriggered.value = true
  try {
    await loadHomeData()
  } finally {
    refresherTriggered.value = false
  }
}

function goDetail(m) {
  const dishId = m && typeof m === 'object' ? m.dishId : m
  if (!dishId) {
    uni.showToast({ title: '该日尚未排餐', icon: 'none' })
    return
  }
  const svc =
    m && typeof m === 'object' && typeof m.serviceDate === 'string' && m.serviceDate.trim()
      ? m.serviceDate.trim()
      : todayYmd.value
  const q = [`dish_id=${encodeURIComponent(dishId)}`]
  if (svc) q.push(`service_date=${encodeURIComponent(svc)}`)
  uni.navigateTo({
    url: `/packageOrder/pages/detail/detail?${q.join('&')}`,
  })
}

function onLoggedIn() {
  couponHostReady.value = true
}

onShareAppMessage(() => ({
  title: 'OK 饭 — 健康自律餐，今日主推新鲜上线',
  path: '/pages/home/index',
}))

onShareTimeline(() => ({
  title: 'OK 饭 — 健康自律餐，今日主推新鲜上线',
  query: '',
}))

onShow(() => {
  if (reLaunchIfCourierModePreferred()) return
  syncCustomTabBar()
  syncTabLayout()
  requestDeliverySubscribeOncePerDay()
  void loadHomeData()
})

onMounted(() => {
  syncTabLayout()
  couponHostReady.value = true
})
</script>

<style lang="scss" scoped>
.page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: $ok-slate-50;
  box-sizing: border-box;
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
  background: $ok-slate-50;
}

.home-page {
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
}
</style>
