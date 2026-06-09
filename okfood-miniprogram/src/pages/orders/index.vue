<template>
  <view class="page">
    <OkNavbar title="订单" />
    <view class="tabs-bar">
      <view
        class="main-tab"
        :class="{ 'main-tab--active': mainTab === 'single' }"
        role="tab"
        :aria-selected="mainTab === 'single'"
        @tap="selectMainTab('single')"
      >
        <text class="main-tab-text">单次点餐订单</text>
      </view>
      <view
        class="main-tab"
        :class="{ 'main-tab--active': mainTab === 'mall' }"
        role="tab"
        :aria-selected="mainTab === 'mall'"
        @tap="selectMainTab('mall')"
      >
        <text class="main-tab-text">商城订单</text>
      </view>
    </view>
    <scroll-view scroll-x class="status-scroll" :show-scrollbar="false" enable-flex>
      <view class="status-row">
        <view
          v-for="s in statusOptions"
          :key="s.id"
          class="status-chip"
          :class="{ 'status-chip--active': listStatus === s.id }"
          @tap="selectStatus(s.id)"
        >
          <text class="status-chip-text">{{ s.label }}</text>
        </view>
      </view>
    </scroll-view>
    <scroll-view
      scroll-y
      class="scroll"
      :style="scrollStyle"
      :show-scrollbar="false"
      lower-threshold="120"
      @scrolltolower="loadMore"
    >
      <view class="list-inner">
        <view v-if="loading && !items.length" class="state-text">加载中&hellip;</view>
        <view v-else-if="!items.length" class="state-text state-text--muted">
          {{ emptyHint }}
        </view>
        <template v-else>
          <template v-if="mainTab === 'single'">
            <view
              v-for="row in items"
              :key="'s-' + row.id"
              class="order-row"
              @tap="openSingleDetail(row.id)"
            >
              <view class="order-row-head">
                <text class="order-title">{{ row.dish_title || '餐品' }}</text>
                <text
                  class="order-amt"
                  :class="{ 'order-amt--card': isSingleMealCardPayLabel(row) }"
                >
                  {{ singleOrderAmountText(row) }}
                </text>
              </view>
              <text class="order-meta">{{ metaLineSingle(row) }}</text>
              <view class="order-foot">
                <text :class="['order-status', `order-status--${statusToneSingle(row)}`]">
                  {{ statusLineSingle(row) }}
                </text>
                <text class="order-arr">&rsaquo;</text>
              </view>
            </view>
          </template>
          <template v-else>
            <view v-for="row in items" :key="'m-' + row.id" class="order-row" @tap="openMallDetail(row)">
              <view class="order-row-head">
                <text class="order-title">{{ mallTitle(row) }}</text>
                <text class="order-amt">¥ {{ row.amount_yuan || '0.00' }}</text>
              </view>
              <text class="order-meta">{{ metaLineMall(row) }}</text>
              <view class="order-foot">
                <text :class="['order-status', `order-status--${statusToneMall(row)}`]">
                  {{ statusLineMall(row) }}
                </text>
                <text class="order-arr">&rsaquo;</text>
              </view>
            </view>
          </template>
          <view v-if="loadingMore" class="state-text state-text--small">加载更多&hellip;</view>
          <view
            v-else-if="items.length && !hasMore"
            class="state-text state-text--small state-text--muted"
          >
            已加载全部
          </view>
        </template>
        <view class="scroll-tail" :style="scrollTailStyle" />
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { showOkAlert } from '@/utils/okAlert.js'
import { getMemberToken, reLaunchIfCourierModePreferred } from '@/utils/api.js'
import { listSingleMealOrders, singleOrderStatusMeta } from '@/utils/singleOrderApi.js'
import { singleMealOrderAmountLabel } from '@/utils/singleOrderPayIntent.js'
import { listMemberCardOrders } from '@/utils/memberCardOrderApi.js'
import { STORAGE_OPEN_ORDERS_PENDING_PAY } from '@/utils/unpaidOrderPrompt.js'
import { syncCustomTabBar, getCustomTabBarBottomReservePx } from '@/utils/customTabBar.js'
import { getPageScrollStyle, ORDERS_TAB_HEADER_CHROME_PX } from '@/utils/navbar.js'

const MAIN_SINGLE = 'single'
const MAIN_MALL = 'mall'

const STATUS_SINGLE = [
  { id: 'all', label: '全部' },
  { id: 'pending_pay', label: '待支付' },
  { id: 'pending_delivery', label: '待送达' },
  { id: 'completed', label: '已完成' },
]

const STATUS_MALL = [
  { id: 'all', label: '全部' },
  { id: 'pending_pay', label: '待支付' },
  { id: 'completed', label: '已完成' },
]

const scrollStyle = ref({})

function applyScrollLayout() {
  const tabBottom = getCustomTabBarBottomReservePx()
  scrollStyle.value = getPageScrollStyle(tabBottom, ORDERS_TAB_HEADER_CHROME_PX)
}

const scrollTailStyle = computed(() => ({
  height: `${getCustomTabBarBottomReservePx()}px`,
}))

const mainTab = ref(MAIN_SINGLE)
const listStatus = ref('all')

const statusOptions = computed(() =>
  mainTab.value === MAIN_SINGLE ? STATUS_SINGLE : STATUS_MALL,
)

const emptyHint = computed(() => {
  if (mainTab.value === MAIN_SINGLE) {
    return '暂无订单。在周菜单中选餐并完成支付后会显示于此。'
  }
  return '暂无商城订单。购买周卡/月卡或卡包并完成支付后会显示于此。'
})

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const loadingMore = ref(false)
let fetchSeq = 0

const hasMore = computed(() => items.value.length < total.value)

function singleOrderAmountText(row) {
  return singleMealOrderAmountLabel(row)
}

function isSingleMealCardPayLabel(row) {
  return singleOrderAmountText(row) === '会员卡支付'
}

function metaLineSingle(o) {
  const d = o?.delivery_date != null ? String(o.delivery_date) : '—'
  const qty = Number(o?.quantity)
  const q = Number.isFinite(qty) && qty >= 1 ? `×${Math.floor(qty)}` : '×1'
  const mode = o?.store_pickup ? '门店自提' : '配送到家'
  return `${d} · ${q} · ${mode}`
}

function statusLineSingle(o) {
  return singleOrderStatusMeta(o || {}).line1 || '—'
}

function statusToneSingle(o) {
  const t = singleOrderStatusMeta(o || {}).tone
  return t === 'warn' || t === 'ok' || t === 'info' ? t : 'info'
}

function mallTitle(row) {
  const r = row?.remark
  if (r && String(r).length > 0) {
    return String(r).replace(/^卡包模版#\d+·/, '卡包 · ')
  }
  const k = row?.card_kind || '会员'
  return `${k} · 开卡订单`
}

function metaLineMall(row) {
  const parts = []
  const ca = row?.created_at
  if (ca) {
    const s = String(ca)
    parts.push(s.length >= 10 ? s.slice(0, 10) : s)
  }
  if (row?.delivery_start_date) {
    parts.push(`起送 ${row.delivery_start_date}`)
  }
  return parts.length ? parts.join(' · ') : '—'
}

function statusLineMall(row) {
  const ps = String(row?.pay_status || '')
  if (ps === '未缴') return '待支付'
  if (ps === '已缴') return '已完成'
  if (ps === '已取消') return '已取消'
  return ps || '—'
}

function statusToneMall(row) {
  const ps = String(row?.pay_status || '')
  if (ps === '未缴') return 'warn'
  if (ps === '已缴') return 'ok'
  if (ps === '已取消') return 'muted'
  return 'info'
}

function selectMainTab(id) {
  if (mainTab.value === id) return
  mainTab.value = id
  listStatus.value = 'all'
  void fetchPage(true)
}

function selectStatus(id) {
  if (listStatus.value === id) return
  listStatus.value = id
  void fetchPage(true)
}

async function fetchPage(reset) {
  const token = getMemberToken()
  const seq = ++fetchSeq
  if (!token) {
    items.value = []
    total.value = 0
    loading.value = false
    loadingMore.value = false
    showOkAlert({
      title: '需要登录',
      content: '请先完成手机号登录后再查看订单。',
      confirmText: '去登录',
      success: (r) => {
        if (r.confirm) uni.switchTab({ url: '/pages/mine/index' })
      },
    })
    return
  }
  if (reset) {
    loading.value = true
    page.value = 1
  } else {
    loadingMore.value = true
  }
  try {
    const p = reset ? 1 : page.value
    const st = listStatus.value === 'all' ? undefined : listStatus.value
    let data
    if (mainTab.value === MAIN_SINGLE) {
      data = await listSingleMealOrders({ page: p, page_size: pageSize, list_status: st })
    } else {
      data = await listMemberCardOrders({ page: p, page_size: pageSize, list_status: st })
    }
    if (seq !== fetchSeq) return
    const list = Array.isArray(data?.items) ? data.items : []
    const t = typeof data?.total === 'number' ? data.total : list.length
    total.value = t
    if (reset) {
      items.value = list
    } else {
      items.value = items.value.concat(list)
    }
    if (!reset && list.length) {
      page.value = p + 1
    }
    if (reset && list.length) {
      page.value = 2
    }
  } catch (e) {
    if (seq !== fetchSeq) return
    if (reset) items.value = []
    uni.showToast({
      title: e instanceof Error ? e.message : '加载失败',
      icon: 'none',
    })
  } finally {
    if (seq === fetchSeq) {
      loading.value = false
      loadingMore.value = false
    }
  }
}

function loadMore() {
  if (!hasMore.value || loading.value || loadingMore.value) return
  void fetchPage(false)
}

function openSingleDetail(orderId) {
  const id = Number(orderId)
  if (!Number.isFinite(id) || id < 1) return
  uni.navigateTo({
    url: `/packageOrder/pages/singleOrderDetail/singleOrderDetail?id=${encodeURIComponent(String(id))}`,
  })
}

function openMallDetail(row) {
  const id = Number(row?.id)
  if (!Number.isFinite(id) || id < 1) return
  uni.navigateTo({
    url: `/packageOrder/pages/memberCardOrderDetail/memberCardOrderDetail?id=${encodeURIComponent(String(id))}`,
  })
}

onShow(() => {
  if (reLaunchIfCourierModePreferred()) return
  applyScrollLayout()
  syncCustomTabBar()
  try {
    const hint = uni.getStorageSync(STORAGE_OPEN_ORDERS_PENDING_PAY)
    if (hint === 'single' || hint === 'mall') {
      uni.removeStorageSync(STORAGE_OPEN_ORDERS_PENDING_PAY)
      mainTab.value = hint === 'mall' ? MAIN_MALL : MAIN_SINGLE
      listStatus.value = 'pending_pay'
    }
  } catch {
    /* ignore */
  }
  void fetchPage(true)
})
</script>

<style lang="scss" scoped>
.page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: $ok-slate-50;
  box-sizing: border-box;
  overflow: hidden;
}

.tabs-bar {
  display: flex;
  gap: 16rpx;
  padding: 16rpx 40rpx 12rpx;
  flex-shrink: 0;
}

.main-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20rpx 16rpx;
  border-radius: 999rpx;
  background: #fff;
  border: 2rpx solid $ok-slate-200;
  box-sizing: border-box;
}

.main-tab--active {
  background: $ok-forest-green;
  border-color: $ok-forest-green;
}

.main-tab-text {
  font-size: 28rpx;
  font-weight: 800;
  color: $ok-slate-600;
  text-align: center;
}

.main-tab--active .main-tab-text {
  color: #fff;
  font-weight: 900;
}

.status-scroll {
  flex-shrink: 0;
  width: 100%;
  white-space: nowrap;
  box-sizing: border-box;
}

.status-row {
  display: inline-flex;
  flex-direction: row;
  flex-wrap: nowrap;
  gap: 12rpx;
  padding: 0 40rpx 16rpx;
  box-sizing: border-box;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 14rpx 28rpx;
  border-radius: 999rpx;
  background: #fff;
  border: 2rpx solid $ok-slate-200;
  flex-shrink: 0;
}

.status-chip--active {
  background: #F4F9F1;
  border-color: rgba(115, 176, 84, 0.35);
}

.status-chip-text {
  font-size: 24rpx;
  font-weight: 800;
  color: $ok-slate-600;
}

.status-chip--active .status-chip-text {
  color: $ok-forest-green;
  font-weight: 900;
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
}

.list-inner {
  padding: 8rpx 40rpx 0;
}

.order-row {
  background: #fff;
  border-radius: 36rpx;
  padding: 28rpx 32rpx;
  margin-bottom: 16rpx;
  border: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
}

.order-row-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
  margin-bottom: 12rpx;
}

.order-title {
  flex: 1;
  min-width: 0;
  font-size: 30rpx;
  font-weight: 950;
  color: #0f172a;
  line-height: 1.35;
}

.order-amt {
  flex-shrink: 0;
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-forest-green;
  font-variant-numeric: tabular-nums;
}

.order-amt--card {
  font-size: 26rpx;
  font-weight: 900;
  max-width: 42%;
  text-align: right;
}

.order-meta {
  display: block;
  font-size: 24rpx;
  font-weight: 750;
  color: $ok-slate-500;
  line-height: 1.45;
}

.order-foot {
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1px dashed rgba(115, 176, 84, 0.15);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.order-status {
  font-size: 26rpx;
  font-weight: 900;
}

.order-status--warn {
  color: #c2410c;
}

.order-status--ok {
  color: #047857;
}

.order-status--muted {
  color: $ok-slate-500;
}

.order-status--info {
  color: #1d4ed8;
}

.order-arr {
  font-size: 32rpx;
  color: #cbd5e1;
}

.state-text {
  padding: 80rpx 20rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.state-text--muted {
  color: $ok-slate-400;
}

.state-text--small {
  padding: 32rpx 20rpx;
  font-size: 24rpx;
  font-weight: 600;
}
</style>
