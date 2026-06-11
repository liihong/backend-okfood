<template>
  <view class="page" :style="pageStyle">
   <OkNavbar title="菜单" />
    <MenuStoreHeader :store-name="storeInfo?.store_name || ''" :store-logo-url="storeInfo?.store_logo_url || ''"
      :store-contact-phone="storeInfo?.store_contact_phone || ''" :fulfill-mode="fulfillMode"
      @change="onFulfillModeChange" />
    <view class="catalog-body" :style="catalogBodyStyle">
      <scroll-view scroll-y class="catalog-sidebar" :show-scrollbar="false">
        <view v-for="cat in sidebarCategories" :key="cat.key" class="sidebar-item"
          :class="{ 'sidebar-item--active': activeCategoryKey === cat.key }" @click="selectCategory(cat.key)">
          <text class="sidebar-item__name">{{ cat.name }}</text>
        </view>
     </scroll-view>

      <scroll-view scroll-y class="catalog-panel" :show-scrollbar="false" refresher-enabled
        :refresher-triggered="refresherTriggered" @refresherrefresh="onMenuRefresherRefresh">
        <view class="catalog-panel__inner">
          <view class="catalog-panel__head">
            <text class="catalog-panel__title">{{ activeCategoryTitle }}</text>
            <text v-if="activeCategoryDesc" class="catalog-panel__desc">{{ activeCategoryDesc }}</text>
          </view>

        <view v-if="panelLoading" class="order-state">加载中…</view>
          <view v-else-if="!displayItems.length" class="order-state order-state--muted">
            {{ emptyText }}
          </view>
         <view v-else class="menu-list">
            <MenuDishCard
              v-for="m in displayItems"
              :key="m.rowKey"
              layout="list"
              :item="m"
              :show-ingredients="true"
              @tap="onItemTap"
            />
          </view>
        </view>
      </scroll-view>
   </view>
    <MemberCouponReminderHost v-if="couponHostReady" />
    <EntryPosterHost />
  </view>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { onShow, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import MenuStoreHeader from '@/components/MenuStoreHeader/MenuStoreHeader.vue'
import MenuDishCard from '@/components/MenuDishCard/MenuDishCard.vue'
import MemberCouponReminderHost from '@/components/MemberCouponReminderHost/MemberCouponReminderHost.vue'
import EntryPosterHost from '@/components/EntryPosterHost/EntryPosterHost.vue'
import { fetchStoreInfo, fetchRetailMenu, mapRetailProductItem } from '@/utils/catalogApi.js'
import {
  addDaysIso,
  fetchWeeklyMenu,
  mondayOfWeekShanghai,
  prefetchWeeklyMenu,
  weeklyMenuItemsHaveStock,
} from '@/utils/menuApi.js'
import { peekWeeklyMenuCache } from '@/utils/weeklyMenuCache.js'
import { getTabPageLayoutStyles } from '@/utils/tabPageLayout.js'
import { getNavbarLayout } from '@/utils/navbar.js'
import { syncCustomTabBar } from '@/utils/customTabBar.js'
import { reLaunchIfCourierModePreferred } from '@/utils/api.js'
import { readMenuFulfillMode, writeMenuFulfillMode } from '@/utils/menuFulfillMode.js'
import { requestDeliverySubscribeOncePerDay } from '@/utils/subscribeMsg.js'
import { RETAIL_ORDER_ENABLED, showRetailComingSoon } from '@/utils/retailFeature.js'

const couponHostReady = ref(false)
const pageStyle = ref({})
const catalogBodyStyle = ref({})
const storeInfo = ref(null)
const retailCategories = ref([])
const loading = ref(true)
const menu = ref([])
const refresherTriggered = ref(false)
const cachedThisWeekMonday = ref('')
const activeCategoryKey = ref('week-this')
const fulfillMode = ref(readMenuFulfillMode())
const nextWeekMenu = ref([])
const nextWeekLoading = ref(false)
let loadWeeklySeq = 0
let loadRetailSeq = 0

const STORE_HEADER_PX = 68

function syncTabLayout() {
  const { pageStyle: p } = getTabPageLayoutStyles()
  pageStyle.value = p
  const win = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
  const pageH = Number(p.height?.replace('px', '')) || Number(win.windowHeight) || 0
  const { navBarTotal } = getNavbarLayout()
  const bodyH = Math.max(200, pageH - navBarTotal - STORE_HEADER_PX)
  catalogBodyStyle.value = { height: `${bodyH}px` }
}

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
  return formatWeekRangeCn(addDaysIso(m, 7))
})

const sidebarCategories = computed(() => {
  const list = [
    {
      key: 'week-this',
      name: '本周',
      type: 'week',
      weekTab: 'this',
    },
    {
      key: 'week-next',
      name: '下周',
      type: 'week',
      weekTab: 'next',
    },
  ]
  for (const c of retailCategories.value) {
    list.push({
      key: `retail-${c.id}`,
      name: c.name,
      type: 'retail',
      categoryId: c.id,
    })
  }
  return list
})

const activeCategoryMeta = computed(() => {
  return sidebarCategories.value.find((c) => c.key === activeCategoryKey.value) || sidebarCategories.value[0]
})

const activeCategoryTitle = computed(() => {
  const meta = activeCategoryMeta.value
  if (!meta) return '本周'
  if (meta.type === 'week') {
    return meta.weekTab === 'next' ? '下周菜单' : '本周菜单'
  }
  return meta.name
})

const activeCategoryDesc = computed(() => {
  const meta = activeCategoryMeta.value
  if (!meta) return ''
  if (meta.type === 'week') {
    const range = meta.weekTab === 'next' ? nextWeekRangeLabel.value : thisWeekRangeLabel.value
    return range ? `${range} 每日新鲜排餐` : '每周新鲜排餐'
  }
  const cat = retailCategories.value.find((c) => c.id === meta.categoryId)
  const count = Array.isArray(cat?.products) ? cat.products.length : 0
  return count > 0 ? `共 ${count} 款商品` : ''
})

const displayItems = computed(() => {
  const meta = activeCategoryMeta.value
  if (!meta) return []
  if (meta.type === 'week') {
    return meta.weekTab === 'next' ? nextWeekMenu.value : menu.value
  }
  const cat = retailCategories.value.find((c) => c.id === meta.categoryId)
  if (!cat || !Array.isArray(cat.products)) return []
  return cat.products.map(mapRetailProductItem)
})

const emptyText = computed(() => {
  const meta = activeCategoryMeta.value
  if (!meta) return '暂无内容'
  if (meta.type === 'week') {
    return meta.weekTab === 'next' ? '下周暂无排餐' : '本周暂无排餐'
  }
  return '该分类暂无商品'
})

const panelLoading = computed(() => {
  const meta = activeCategoryMeta.value
  if (!meta) return loading.value
  if (meta.type === 'week' && meta.weekTab === 'next') {
    return nextWeekLoading.value && !nextWeekMenu.value.length
  }
  if (meta.type === 'week') return loading.value && !menu.value.length
  return false
})

function selectCategory(key) {
  if (activeCategoryKey.value === key) return
  activeCategoryKey.value = key
  const meta = sidebarCategories.value.find((c) => c.key === key)
  if (meta?.type === 'retail') {
    void loadRetailCatalog({ forceRefresh: true })
    return
  }
  if (meta?.type === 'week' && meta.weekTab === 'next' && !nextWeekMenu.value.length) {
    loadNextWeek()
  }
}

async function loadThisWeek(opts = {}) {
  const forceRefresh = opts.forceRefresh === true
  const seq = ++loadWeeklySeq
  const cached = peekWeeklyMenuCache({})
  const cacheHasStock = cached ? weeklyMenuItemsHaveStock(cached.items) : false

  if (cached && !forceRefresh) {
    if (seq !== loadWeeklySeq) return
    menu.value = cached.items
    if (cached.weekStart) cachedThisWeekMonday.value = cached.weekStart
    loading.value = false
    if (!cached.stale && cacheHasStock) {
      if (cached.weekStart) prefetchWeeklyMenu({ weekStart: addDaysIso(cached.weekStart, 7) })
      return
    }
  } else if (!forceRefresh) {
    loading.value = true
  }

  try {
    const fresh = await fetchWeeklyMenu({
      includeStock: true,
      forceRefresh: forceRefresh || !!cached?.stale || !cacheHasStock,
    })
    if (seq !== loadWeeklySeq) return
    if (fresh.weekStart) cachedThisWeekMonday.value = fresh.weekStart
    menu.value = fresh.items
    if (fresh.weekStart) prefetchWeeklyMenu({ weekStart: addDaysIso(fresh.weekStart, 7) })
  } catch (e) {
    if (seq !== loadWeeklySeq) return
    if (!cached) {
      menu.value = []
      const msg = e?.message || '加载失败'
      setTimeout(() => uni.showToast({ title: msg, icon: 'none' }), 80)
    }
  } finally {
    if (seq === loadWeeklySeq) loading.value = false
  }
}

async function loadNextWeek(opts = {}) {
  const forceRefresh = opts.forceRefresh === true
  if (nextWeekLoading.value && !forceRefresh) return
  nextWeekLoading.value = true

  const mon =
    cachedThisWeekMonday.value ||
    peekWeeklyMenuCache({})?.weekStart ||
    mondayOfWeekShanghai()
  const requestWeekStart = mon ? addDaysIso(mon, 7) : ''
  const cacheOpts = requestWeekStart ? { weekStart: requestWeekStart } : {}
  const cached = peekWeeklyMenuCache(cacheOpts)
  const cacheHasStock = cached ? weeklyMenuItemsHaveStock(cached.items) : false

  try {
    if (cached && !forceRefresh && !cached.stale && cacheHasStock) {
      nextWeekMenu.value = cached.items
      return
    }
    const fresh = await fetchWeeklyMenu({
      ...cacheOpts,
      includeStock: true,
      forceRefresh: forceRefresh || !!cached?.stale || !cacheHasStock,
    })
    nextWeekMenu.value = fresh.items
  } catch (e) {
    if (!cached) nextWeekMenu.value = []
  } finally {
    nextWeekLoading.value = false
  }
}

async function loadRetailCatalog(opts = {}) {
  const forceRefresh = opts.forceRefresh === true
  const seq = ++loadRetailSeq
  try {
    const data = await fetchRetailMenu()
    if (seq !== loadRetailSeq) return
    retailCategories.value = Array.isArray(data) ? data : []
  } catch {
    if (seq !== loadRetailSeq) return
    if (forceRefresh || !retailCategories.value.length) retailCategories.value = []
  }
}

async function loadStoreInfo() {
  try {
    storeInfo.value = await fetchStoreInfo()
  } catch {
    storeInfo.value = null
  }
}

async function loadPageData(opts = {}) {
  await Promise.all([loadThisWeek(opts), loadRetailCatalog(opts), loadStoreInfo()])
  if (activeCategoryMeta.value?.type === 'week' && activeCategoryMeta.value.weekTab === 'next') {
    await loadNextWeek(opts)
  }
}

async function onMenuRefresherRefresh() {
  refresherTriggered.value = true
  try {
    await loadPageData({ forceRefresh: true })
    if (activeCategoryMeta.value?.type === 'week' && activeCategoryMeta.value.weekTab === 'next') {
      await loadNextWeek({ forceRefresh: true })
    }
  } finally {
    refresherTriggered.value = false
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
  requestDeliverySubscribeOncePerDay()
  loadPageData()
})

onMounted(() => {
  syncTabLayout()
  couponHostReady.value = true
})

watch(fulfillMode, (v) => {
  writeMenuFulfillMode(v)
})

function onFulfillModeChange(mode) {
  fulfillMode.value = mode === 'pickup' ? 'pickup' : 'delivery'
}

function onItemTap(m) {
  if (m?.isRetail) {
    if (!RETAIL_ORDER_ENABLED) {
      showRetailComingSoon()
      return
    }
    const pid = m?.retailProductId != null ? Number(m.retailProductId) : 0
    if (!Number.isFinite(pid) || pid < 1) {
      uni.showToast({ title: '商品无效', icon: 'none' })
      return
    }
    uni.navigateTo({
      url: `/packageOrder/pages/retailConfirm/retailConfirm?retail_product_id=${encodeURIComponent(String(pid))}`,
    })
    return
  }
  goDetail(m)
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
      : ''
  const q = [`dish_id=${encodeURIComponent(dishId)}`]
  if (svc) q.push(`service_date=${encodeURIComponent(svc)}`)
  uni.navigateTo({
    url: `/packageOrder/pages/detail/detail?${q.join('&')}`,
  })
}
</script>

<style lang="scss" scoped>
.page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: $ok-slate-50;
  box-sizing: border-box;
  overflow: hidden;
}

.catalog-body {
  flex: 1;
  min-height: 0;
  display: flex;
    flex-direction: row;
    overflow: hidden;
}

.catalog-sidebar {
  width: 176rpx;
  flex-shrink: 0;
  height: 100%;
  background: #f1f5f9;
}

.sidebar-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4rpx;
    min-height: 112rpx;
    padding: 16rpx 12rpx;
  box-sizing: border-box;
}

.sidebar-item--active {
  background: #fff;
}

.sidebar-item--active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 24rpx;
  bottom: 24rpx;
  width: 6rpx;
  border-radius: 0 6rpx 6rpx 0;
  background: $ok-forest-green;
}

.sidebar-item__name {
  font-size: 26rpx;
  font-weight: 800;
  color: $ok-slate-600;
  text-align: center;
  line-height: 1.3;
  }
  
  .sidebar-item--active .sidebar-item__name {
    color: $ok-forest-green;
    font-weight: 900;
  }
  
  .catalog-panel {
    flex: 1;
    min-width: 0;
    height: 100%;
    background: #fff;
  }
  
  .catalog-panel__inner {
    padding: 24rpx 24rpx calc(24rpx + env(safe-area-inset-bottom));
}

.catalog-panel__head {
  margin-bottom: 20rpx;
}

.catalog-panel__title {
  display: block;
  font-size: 30rpx;
  font-weight: 900;
  color: #1e293b;
  line-height: 1.3;
}

.catalog-panel__desc {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: $ok-slate-400;
  font-weight: 600;
  line-height: 1.3;
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

.menu-list {
  display: flex;
  flex-direction: column;
}
</style>
