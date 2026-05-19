<template>
  <view class="page">
    <OkNavbar show-back title="我的订单" />
    <scroll-view
      scroll-y
      class="scroll"
      :show-scrollbar="false"
      lower-threshold="120"
      @scrolltolower="loadMore"
    >
      <view class="list-inner">
        <view class="scope-hint">
          <text class="scope-hint-title">单次点餐订单</text>
          <text class="scope-hint-sub">以下为单点菜的支付与履约状态；商城自营等其它订单将陆续接入此处。</text>
        </view>
        <view v-if="loading && !items.length" class="state-text">加载中…</view>
        <view v-else-if="!items.length" class="state-text state-text--muted">
          暂无订单。在周菜单中选餐并完成支付后会显示于此。
        </view>
        <template v-else>
          <view
            v-for="row in items"
            :key="row.id"
            class="order-row"
            @tap="openDetail(row.id)"
          >
            <view class="order-row-head">
              <text class="order-title">{{ row.dish_title || '餐品' }}</text>
              <text class="order-amt">¥ {{ row.amount_yuan || '0.00' }}</text>
            </view>
            <text class="order-meta">{{ metaLine(row) }}</text>
            <view class="order-foot">
              <text :class="['order-status', `order-status--${statusTone(row)}`]">
                {{ statusLine(row) }}
              </text>
              <text class="order-arr">›</text>
            </view>
          </view>
          <view v-if="loadingMore" class="state-text state-text--small">加载更多…</view>
          <view
            v-else-if="items.length && !hasMore"
            class="state-text state-text--small state-text--muted"
          >
            已加载全部
          </view>
        </template>
        <view class="scroll-tail" />
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getMemberToken } from '@/utils/api.js'
import { listSingleMealOrders, singleOrderStatusMeta } from '@/utils/singleOrderApi.js'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const loadingMore = ref(false)
let fetchSeq = 0

const hasMore = computed(() => items.value.length < total.value)

function metaLine(o) {
  const d = o?.delivery_date != null ? String(o.delivery_date) : '—'
  const qty = Number(o?.quantity)
  const q =
    Number.isFinite(qty) && qty >= 1 ? `×${Math.floor(qty)}` : '×1'
  const mode = o?.store_pickup ? '门店自提' : '配送到家'
  return `${d} · ${q} · ${mode}`
}

function statusLine(o) {
  return singleOrderStatusMeta(o || {}).line1 || '—'
}

function statusTone(o) {
  const t = singleOrderStatusMeta(o || {}).tone
  return t === 'warn' || t === 'ok' || t === 'info' ? t : 'info'
}

async function fetchPage(reset) {
  const token = getMemberToken()
  const seq = ++fetchSeq
  if (!token) {
    items.value = []
    total.value = 0
    loading.value = false
    loadingMore.value = false
    uni.showModal({
      title: '需要登录',
      content: '请先完成手机号登录后再查看订单。',
      confirmText: '去登录',
      success: (r) => {
        if (r.confirm) uni.switchTab({ url: '/pages/mine/index' })
        else uni.navigateBack()
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
    const data = await listSingleMealOrders({ page: p, page_size: pageSize })
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

function openDetail(orderId) {
  const id = Number(orderId)
  if (!Number.isFinite(id) || id < 1) return
  uni.navigateTo({
    url: `/packageOrder/pages/singleOrderDetail/singleOrderDetail?id=${encodeURIComponent(String(id))}`,
  })
}

onShow(() => {
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
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
}

.list-inner {
  padding: 24rpx 40rpx 0;
}

.scope-hint {
  background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
  border-radius: 36rpx;
  padding: 28rpx 32rpx;
  margin-bottom: 24rpx;
  border: 1px solid rgba(14, 90, 68, 0.12);
}

.scope-hint-title {
  display: block;
  font-size: 28rpx;
  font-weight: 950;
  color: $ok-forest-green;
  margin-bottom: 12rpx;
}

.scope-hint-sub {
  display: block;
  font-size: 22rpx;
  font-weight: 650;
  color: $ok-slate-500;
  line-height: 1.5;
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
  border-top: 1px dashed rgba(14, 90, 68, 0.15);
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

.scroll-tail {
  height: calc(24rpx + env(safe-area-inset-bottom));
}
</style>
