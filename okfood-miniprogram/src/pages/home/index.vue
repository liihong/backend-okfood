<template>
  <view class="page paper-background" :style="pageStyle">
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
        <view class="home-hero">
          <HomeBannerSwiper :banners="banners" :today-ymd="todayYmd" />
          <view class="home-hero__member">
            <MemberLoginPromptBar @logged-in="onLoggedIn" />
          </view>
        </view>
        <view class="home-cards">
          <HomeMembershipCardStrip :templates="cardTemplates" />
        </view>
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
import HomeMembershipCardStrip from '@/components/HomeMembershipCardStrip/HomeMembershipCardStrip.vue'
import MemberCouponReminderHost from '@/components/MemberCouponReminderHost/MemberCouponReminderHost.vue'
import { fetchHomeBanners, fetchHomeMembershipCards } from '@/utils/homeApi.js'
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
const cardTemplates = ref([])
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
    const [bannerList, dish, cardList] = await Promise.all([
      fetchHomeBanners().catch(() => []),
      fetchTodayMenu().catch(() => null),
      fetchHomeMembershipCards().catch(() => []),
    ])
    if (seq !== loadSeq) return
    banners.value = bannerList
    todayDish.value = dish
    cardTemplates.value = Array.isArray(cardList) ? cardList : []
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
  void loadHomeData()
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
  box-sizing: border-box;
  overflow: hidden;
}

.paper-background {
  background-color: #f7f5f0;
  background-image:
    radial-gradient(circle at 50% 50%, rgba(255, 255, 255, 0.65), rgba(185, 184, 180, 0)),
    url("data:image/svg+xml;base64,PHN2ZyB2aWV3Qm94PSIwIDAgMjAwIDIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZmlsdGVyIGlkPSJub2lzZSI+PGZlVHVyYnVsZW5jZSB0eXBlPSJmcmFjdGFsTm9pc2UiIGJhc2VGcmVxdWVuY3k9IjAuMzUiIG51bU9jdGF2ZXM9IjMiIHN0aXRjaFRpbGVzPSJzdGl0Y2giLz48ZmVDb2xvck1hdHJpeCB0eXBlPSJtYXRyaXgiIHZhbHVlcz0iMCAwIDAgMCAwIDAgMCAwIDAgMCAwIDAgMCAwIDAgMC4wMyAwIDAgMCAwIi8+PC9maWx0ZXI+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsdGVyPSJ1cmwoI25vaXNlKSIvPjwvc3ZnPg==");
  background-blend-mode: multiply;
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
  background: transparent;
}

.home-page {
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
}

.home-hero {
  position: relative;
}

.home-hero :deep(.home-banner-swiper) {
  margin-bottom: 0;
}

.home-hero__member {
  position: relative;
  z-index: 2;
  margin-top: -44rpx;
}

.home-cards {
  position: relative;
  z-index: 1;
  margin-top: 24rpx;
}
</style>
