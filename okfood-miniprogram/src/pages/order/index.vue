<template>
  <view class="page" :style="pageStyle">
    <OkNavbar show-brand show-rider-entry />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="order-page">
        <view class="week-tabs" role="tablist">
          <view
            class="week-tab"
            :class="{ 'week-tab--active': activeWeekTab === 'this' }"
            role="tab"
            :aria-selected="activeWeekTab === 'this'"
            @click="selectWeekTab('this')"
          >
            <text class="week-tab-text">本周菜单</text>
            <text v-if="thisWeekRangeLabel" class="week-tab-sub">{{ thisWeekRangeLabel }}</text>
          </view>
          <view
            class="week-tab"
            :class="{ 'week-tab--active': activeWeekTab === 'next' }"
            role="tab"
            :aria-selected="activeWeekTab === 'next'"
            @click="selectWeekTab('next')"
          >
            <text class="week-tab-text">下周菜单</text>
            <text v-if="nextWeekRangeLabel" class="week-tab-sub">{{ nextWeekRangeLabel }}</text>
          </view>
        </view>

        <view v-if="loading" class="order-state">加载中…</view>
        <view v-else-if="!menu.length" class="order-state order-state--muted">
          {{ activeWeekTab === 'this' ? '本周暂无排餐' : '下周暂无排餐' }}
        </view>
        <view v-else class="menu-grid">
          <view v-for="m in menu" :key="m.rowKey" class="dish-card" @click="goDetail(m)">
            <view class="dish-img-wrap">
              <text class="day-label-tag">{{ m.day }}</text>
              <image
                class="dish-img"
                :src="m.img"
                mode="aspectFill"
                @error="() => onImgErr(m)"
              />
            </view>
            <view class="dish-body">
              <text class="dish-name">{{ m.name }}</text>
              <view class="price-row">
                <text class="price-label">自律体验价</text>
                <text
                  v-if="formatMenuPrice(m.price) != null"
                  class="price-val"
                >¥{{ formatMenuPrice(m.price) }}</text>
                <text v-else class="price-val price-val--pending">待公布</text>
              </view>
              <text class="dish-ingredients">配料：{{ m.ingredients }}</text>
              <!-- <button
                v-if="isSingleOrderServiceDate(m.serviceDate)"
                class="btn-quick-buy"
                @click.stop="goDetail(m)"
              >立即下单</button> -->
            </view>
          </view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { onShow, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  addDaysIso,
  fetchWeeklyMenu,
  formatMenuPrice,
  isSingleOrderServiceDate,
} from '@/utils/menuApi.js'
import { getTabPageLayoutStyles } from '@/utils/tabPageLayout.js'
import { syncCustomTabBar } from '@/utils/customTabBar.js'
import { reLaunchIfCourierModePreferred } from '@/utils/api.js'
import { requestDeliverySubscribeOncePerDay } from '@/utils/subscribeMsg.js'

const pageStyle = ref({})
const scrollStyle = ref({})

function syncTabLayout() {
  const { pageStyle: p, scrollStyle: s } = getTabPageLayoutStyles()
  pageStyle.value = p
  scrollStyle.value = s
}

const loading = ref(true)
const menu = ref([])
/** 当前页「本周」周一（YYYY-MM-DD），用于请求「下周」时 +7，避免与后台业务周不一致 */
const cachedThisWeekMonday = ref('')
/** `this` 本周 | `next` 下周，与后台 `GET /api/menu/weekly` 及 `week_start` 一致 */
const activeWeekTab = ref('this')
/** 避免 onShow 重复触发时多个请求同时结束，连续 showToast 触发基础库 timeout */
let loadWeeklySeq = 0

/** @param {string} mondayIso 当周周一 YYYY-MM-DD */
function formatWeekRangeCn(mondayIso) {
  if (!mondayIso || typeof mondayIso !== 'string') return ''
  const sunIso = addDaysIso(mondayIso.trim(), 6)
  if (!sunIso) return ''
  const d0 = new Date(`${mondayIso.trim()}T12:00:00`)
  const d1 = new Date(`${sunIso}T12:00:00`)
  if (Number.isNaN(d0.getTime()) || Number.isNaN(d1.getTime())) return ''
  const a = `${d0.getMonth() + 1}月${d0.getDate()}日`
  const b = `${d1.getMonth() + 1}月${d1.getDate()}日`
  return `${a}~${b}`
}

const thisWeekRangeLabel = computed(() => formatWeekRangeCn(cachedThisWeekMonday.value))

const nextWeekRangeLabel = computed(() => {
  const m = cachedThisWeekMonday.value
  if (!m) return ''
  const nextMon = addDaysIso(m, 7)
  return formatWeekRangeCn(nextMon)
})

function selectWeekTab(tab) {
  if (activeWeekTab.value === tab) return
  activeWeekTab.value = tab
  loadWeekly()
}

async function loadWeekly() {
  const seq = ++loadWeeklySeq
  loading.value = true
  try {
    if (activeWeekTab.value === 'this') {
      const { weekStart, items } = await fetchWeeklyMenu()
      if (seq !== loadWeeklySeq) return
      if (weekStart) cachedThisWeekMonday.value = weekStart
      menu.value = items
    } else {
      let monday = cachedThisWeekMonday.value
      if (!monday) {
        const tw = await fetchWeeklyMenu()
        if (seq !== loadWeeklySeq) return
        monday = tw.weekStart
        if (monday) cachedThisWeekMonday.value = monday
      }
      const nextMonday = monday ? addDaysIso(monday, 7) : ''
      if (!nextMonday) {
        menu.value = []
      } else {
        const { items } = await fetchWeeklyMenu({ weekStart: nextMonday })
        if (seq !== loadWeeklySeq) return
        menu.value = items
      }
    }
  } catch (e) {
    if (seq !== loadWeeklySeq) return
    const msg = e?.message || '加载失败'
    menu.value = []
    setTimeout(() => {
      uni.showToast({ title: msg, icon: 'none' })
    }, 80)
  } finally {
    if (seq === loadWeeklySeq) loading.value = false
  }
}

const homeSharePath = '/pages/order/index'

onShareAppMessage(() => ({
  title: 'OK 饭 — 健康自律餐，每周新鲜菜单',
  path: homeSharePath,
}))

onShareTimeline(() => ({
  title: 'OK 饭 — 健康自律餐，每周新鲜菜单',
  query: '',
}))

onShow(() => {
  if (reLaunchIfCourierModePreferred()) return
  syncCustomTabBar()
  syncTabLayout()
  cachedThisWeekMonday.value = ''
  requestDeliverySubscribeOncePerDay()
  loadWeekly()
})

onMounted(() => {
  syncTabLayout()
})

function goDetail(m) {
  const dishId = m && typeof m === 'object' ? m.dishId : m
  if (!dishId) {
    uni.showToast({ title: '该日尚未排餐', icon: 'none' })
    return
  }
  const svc =
    m && typeof m === 'object' && typeof m.serviceDate === 'string' && m.serviceDate.trim()
      ? m.serviceDate.trim()
      : ''
  const q = [`dish_id=${encodeURIComponent(dishId)}`]
  if (svc) q.push(`service_date=${encodeURIComponent(svc)}`)
  uni.navigateTo({
    url: `/packageOrder/pages/detail/detail?${q.join('&')}`,
  })
}

const fallbackImg =
  'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400'

function onImgErr(item) {
  if (item) item.img = fallbackImg
}
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

.order-page {
  padding: 40rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
}

.week-tabs {
  display: flex;
  gap: 20rpx;
  margin-bottom: 40rpx;
}

.week-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6rpx;
  padding: 18rpx 16rpx 20rpx;
  border-radius: 999rpx;
  background: #fff;
  border: 2rpx solid $ok-slate-200;
  box-sizing: border-box;
}

.week-tab--active {
  background: $ok-forest-green;
  border-color: $ok-forest-green;
}

.week-tab-text {
  font-size: 28rpx;
  font-weight: 900;
  color: $ok-slate-600;
  text-align: center;
}

.week-tab--active .week-tab-text {
  color: #fff;
}

.week-tab-sub {
  font-size: 20rpx;
  font-weight: 800;
  color: $ok-slate-400;
  line-height: 1.2;
  text-align: center;
}

.week-tab--active .week-tab-sub {
  color: rgba(255, 255, 255, 0.9);
}

.order-state {
  padding: 80rpx 20rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.order-state--muted {
  color: $ok-slate-400;
}

.menu-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 30rpx;
}

.dish-card {
  background: #fff;
  border-radius: 48rpx;
  overflow: hidden;
  border: 1px solid $ok-slate-100;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
}

.dish-img-wrap {
  width: 100%;
  aspect-ratio: 1;
  background: $ok-slate-50;
  position: relative;
  overflow: hidden;
}

.dish-img {
  width: 100%;
  height: 100%;
}

.day-label-tag {
  position: absolute;
  top: 20rpx;
  left: 20rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 24rpx;
  font-weight: 900;
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
  z-index: 10;
}

.dish-body {
  padding: 24rpx;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.dish-name {
  font-size: 26rpx;
  font-weight: 950;
  color: #333;
  margin-bottom: 4rpx;
}

.price-row {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
  margin-bottom: 12rpx;
}

.price-label {
  font-size: 16rpx;
  color: $ok-slate-400;
  font-weight: 900;
}

.price-val {
  font-size: 32rpx;
  font-weight: 1000;
  font-style: italic;
  color: $ok-forest-green;
}

.price-val--pending {
  font-size: 26rpx;
  font-style: normal;
  font-weight: 800;
  color: $ok-slate-400;
}

.dish-ingredients {
  font-size: 18rpx;
  color: $ok-slate-400;
  line-height: 1.4;
  font-weight: 700;
  margin-bottom: 24rpx;
  max-height: 2.8em;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.btn-quick-buy {
  width: 100%;
  padding: 20rpx;
  background: $ok-forest-green;
  color: #fff;
  border: none;
  border-radius: 24rpx;
  font-size: 22rpx;
  font-weight: 900;
  margin-top: auto;
}

</style>
