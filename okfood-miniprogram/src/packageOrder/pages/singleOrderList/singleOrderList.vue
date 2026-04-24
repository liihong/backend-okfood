<template>
  <view class="page">
    <OkNavbar show-back title="我的单次订单" />
    <scroll-view
      scroll-y
      class="scroll"
      :show-scrollbar="false"
      lower-threshold="120"
      @scrolltolower="loadMore"
    >
      <view class="list-inner">
        <view v-if="loading && !items.length" class="state-text">加载中…</view>
        <view v-else-if="!items.length" class="state-text state-text--muted">
          暂无单次点餐订单，可在「菜单」中选购
        </view>
        <template v-else>
          <view
            v-for="row in items"
            :key="row.id"
            class="order-card"
            @click="goDetail(row.id)"
          >
            <view class="card-top">
              <text class="order-no">单号 {{ row.out_trade_no || row.id }}</text>
              <text :class="['status-pill', `status-pill--${statusTone(row)}`]">
                {{ statusLine(row) }}
              </text>
            </view>
            <text class="dish-title">{{ row.dish_title || '餐品' }}</text>
            <view class="card-meta">
              <text class="meta">供餐日 {{ row.delivery_date || '—' }}</text>
              <text class="meta">×{{ row.quantity ?? 1 }}</text>
            </view>
            <view class="card-foot">
              <text class="amt">¥ {{ row.amount_yuan || '0.00' }}</text>
              <text class="chevron">详情 ›</text>
            </view>
          </view>
        </template>
        <view v-if="loadingMore" class="state-text state-text--small">加载更多…</view>
        <view v-else-if="items.length && !hasMore" class="state-text state-text--small state-text--muted">
          已加载全部
        </view>
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

function statusLine(row) {
  return singleOrderStatusMeta(row).line1
}

function statusTone(row) {
  return singleOrderStatusMeta(row).tone
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

onShow(() => {
  void fetchPage(true)
})

function goDetail(id) {
  if (id == null) return
  uni.navigateTo({
    url: `/packageOrder/pages/singleOrderDetail/singleOrderDetail?id=${encodeURIComponent(String(id))}`,
  })
}
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

.order-card {
  background: #fff;
  border-radius: 48rpx;
  padding: 36rpx 40rpx;
  margin-bottom: 24rpx;
  border: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.order-no {
  font-size: 24rpx;
  color: $ok-slate-400;
  font-weight: 700;
  flex: 1;
  min-width: 0;
}

.status-pill {
  font-size: 22rpx;
  font-weight: 900;
  padding: 6rpx 18rpx;
  border-radius: 999rpx;
  flex-shrink: 0;
}

.status-pill--warn {
  background: #fff7ed;
  color: #c2410c;
}

.status-pill--ok {
  background: #ecfdf5;
  color: #047857;
}

.status-pill--info {
  background: #eff6ff;
  color: #1d4ed8;
}

.dish-title {
  display: block;
  font-size: 32rpx;
  font-weight: 950;
  color: #333;
  line-height: 1.35;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  margin-top: 12rpx;
}

.meta {
  font-size: 24rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.amt {
  font-size: 34rpx;
  font-weight: 950;
  color: $ok-forest-green;
}

.chevron {
  font-size: 26rpx;
  color: $ok-slate-400;
  font-weight: 800;
}

.scroll-tail {
  height: calc(24rpx + env(safe-area-inset-bottom));
}
</style>
