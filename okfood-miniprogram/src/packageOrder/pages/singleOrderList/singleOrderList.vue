<template>
  <view class="page">
   <OkNavbar show-back title="消费记录" />
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
         暂无扣次记录。套餐配送在确认送达、扣减「剩余餐次」后，会按配送业务日显示在此。
        </view>
        <template v-else>
         <view v-if="total > 0" class="summary-card">
            <text class="summary-title">累计消费</text>
            <text class="summary-num">{{ totalMealUnits }} 份餐</text>
            <text class="summary-hint">共 {{ total }} 个配送日 · 下列为每次扣次对应的配送日期与份数</text>
          </view>
         <view v-for="(row, idx) in items" :key="row.delivery_date + '-' + idx" class="record-row">
            <view class="record-main">
              <text class="record-label">配送日</text>
              <text class="record-date">{{ row.delivery_date || '—' }}</text>
            </view>
            <text class="record-units">{{ row.meal_units || 1 }} 份</text>
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
import { showOkAlert } from '@/utils/okAlert.js'
import { getMemberToken } from '@/utils/api.js'
import { listDeliveryDeductions } from '@/utils/deliveryDeductionApi.js'

const items = ref([])
const total = ref(0)
const totalMealUnits = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const loadingMore = ref(false)
let fetchSeq = 0

const hasMore = computed(() => items.value.length < total.value)

async function fetchPage(reset) {
  const token = getMemberToken()
  const seq = ++fetchSeq
  if (!token) {
    items.value = []
    total.value = 0
    totalMealUnits.value = 0
    loading.value = false
    loadingMore.value = false
    showOkAlert({
      title: '需要登录',
      content: '请先完成手机号登录后再查看消费记录。',
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
    const data = await listDeliveryDeductions({ page: p, page_size: pageSize })
    if (seq !== fetchSeq) return
    const list = Array.isArray(data?.items) ? data.items : []
    const t = typeof data?.total === 'number' ? data.total : list.length
    total.value = t
    totalMealUnits.value = typeof data?.total_meal_units === 'number' ? data.total_meal_units : 0
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

.summary-card {
  background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
  border-radius: 36rpx;
  padding: 32rpx 36rpx;
  margin-bottom: 24rpx;
  border: 1px solid rgba(14, 90, 68, 0.12);
}

.summary-title {
  display: block;
  font-size: 26rpx;
  font-weight: 800;
  color: $ok-slate-500;
  margin-bottom: 8rpx;
}

.summary-num {
  display: block;
  font-size: 44rpx;
  font-weight: 950;
  color: $ok-forest-green;
  line-height: 1.2;
  margin-bottom: 12rpx;
}

.summary-hint {
  display: block;
  font-size: 22rpx;
  color: $ok-slate-400;
  font-weight: 600;
  line-height: 1.45;
}

.record-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
    background: #fff;
    border-radius: 36rpx;
    padding: 32rpx 40rpx;
  margin-bottom: 16rpx;
  border: 1px solid rgba(0, 0, 0, 0.04);
    box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
}

.record-main {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  min-width: 0;
  flex: 1;
}

.record-label {
  font-size: 28rpx;
  font-weight: 800;
  color: $ok-slate-500;
}

.record-date {
  font-size: 30rpx;
  font-weight: 900;
  color: #333;
  font-variant-numeric: tabular-nums;
}

.record-units {
  flex-shrink: 0;
  font-size: 28rpx;
  font-weight: 900;
  color: $ok-forest-green;
  font-variant-numeric: tabular-nums;
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
