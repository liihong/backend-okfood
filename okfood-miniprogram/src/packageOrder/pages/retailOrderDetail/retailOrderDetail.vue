<template>
  <view class="page">
    <OkNavbar show-back title="商城订单详情" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view v-if="loading" class="state">加载中…</view>
      <view v-else-if="loadError" class="state state--err">{{ loadError }}</view>
      <view v-else-if="order" class="body">
        <view class="card">
          <text class="status" :class="`status--${status.tone}`">{{ status.line1 }}</text>
          <text class="status-sub">{{ status.line2 }}</text>
        </view>
        <view class="card">
          <view class="row"><text class="label">商品</text><text class="value">{{ order.product_title }}</text></view>
          <view class="row"><text class="label">数量</text><text class="value">×{{ order.quantity }}</text></view>
          <view class="row"><text class="label">金额</text><text class="value amt">¥ {{ order.amount_yuan }}</text></view>
        </view>
        <view class="card">
          <view class="row"><text class="label">方式</text><text class="value">{{ order.store_pickup ? '门店自提' : '配送到家' }}</text></view>
          <view class="row block"><text class="label">地址</text><text class="value">{{ order.address_summary || '—' }}</text></view>
        </view>
        <view class="card">
          <view class="row"><text class="label">单号</text><text class="value mono">{{ order.out_trade_no }}</text></view>
          <view class="row"><text class="label">下单</text><text class="value">{{ createdAtText }}</text></view>
        </view>
        <button
          v-if="order.pay_status === '未支付' && order.fulfillment_status === 'pending'"
          class="btn-pay"
          :disabled="paying"
          @tap="continuePay"
        >
          {{ paying ? '处理中…' : '继续支付' }}
        </button>
        <button
          v-if="canCancel"
          class="btn-cancel"
          :disabled="cancelling"
          @tap="onCancel"
        >
          {{ cancelling ? '取消中…' : '取消订单' }}
        </button>
        <view class="tail" />
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getPageScrollStyle } from '@/utils/navbar.js'
import { getMemberToken } from '@/utils/api.js'
import {
  canCancelRetailOrder,
  cancelRetailOrder,
  formatRetailOrderCreatedAt,
  getRetailOrder,
  retailOrderStatusMeta,
} from '@/utils/retailOrder/retailOrderApi.js'
import { payRetailOrderWechat } from '@/utils/retailOrder/retailOrderPay.js'
import { showOkAlert } from '@/utils/okAlert.js'

const scrollStyle = ref(getPageScrollStyle())
const orderId = ref(0)
const order = ref(null)
const loading = ref(true)
const loadError = ref('')
const paying = ref(false)
const cancelling = ref(false)

const status = computed(() => retailOrderStatusMeta(order.value || {}))
const createdAtText = computed(() => formatRetailOrderCreatedAt(order.value?.created_at))
const canCancel = computed(() => canCancelRetailOrder(order.value))

async function loadOrder() {
  if (!orderId.value) return
  loading.value = true
  loadError.value = ''
  try {
    order.value = await getRetailOrder(orderId.value)
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function continuePay() {
  if (paying.value || !order.value) return
  paying.value = true
  try {
    const r = await payRetailOrderWechat(orderId.value)
    if (!r.paySynced) {
      uni.showToast({ title: '支付成功，同步中请稍后刷新', icon: 'none' })
    }
    await loadOrder()
  } catch (e) {
    uni.showToast({ title: e instanceof Error ? e.message : '支付失败', icon: 'none' })
  } finally {
    paying.value = false
  }
}

function onCancel() {
  if (cancelling.value) return
  showOkAlert({
    title: '取消订单',
    content: '确定取消该商城订单？',
    success: async (res) => {
      if (!res.confirm) return
      cancelling.value = true
      try {
        await cancelRetailOrder(orderId.value)
        await loadOrder()
        uni.showToast({ title: '已取消', icon: 'none' })
      } catch (e) {
        uni.showToast({ title: e instanceof Error ? e.message : '取消失败', icon: 'none' })
      } finally {
        cancelling.value = false
      }
    },
  })
}

onLoad((options) => {
  const id = Math.floor(Number(options?.id || 0))
  if (!Number.isFinite(id) || id < 1) {
    loadError.value = '订单无效'
    loading.value = false
    return
  }
  orderId.value = id
  if (!getMemberToken()) {
    loadError.value = '请先登录'
    loading.value = false
    return
  }
  void loadOrder()
})

onShow(() => {
  if (orderId.value && getMemberToken()) void loadOrder()
})
</script>

<style lang="scss" scoped>
.page { height: 100vh; display: flex; flex-direction: column; background: #f8fafc; }
.scroll { flex: 1; min-height: 0; }
.body { padding: 24rpx; }
.card { background: #fff; border-radius: 20rpx; padding: 28rpx; margin-bottom: 20rpx; }
.row { display: flex; justify-content: space-between; gap: 16rpx; padding: 12rpx 0; font-size: 28rpx; }
.row.block { flex-direction: column; }
.label { color: #64748b; }
.value { color: #0f172a; text-align: right; }
.amt { color: #73b054; font-weight: 800; }
.mono { font-family: monospace; font-size: 24rpx; }
.status { font-size: 34rpx; font-weight: 800; display: block; }
.status--ok { color: #16a34a; }
.status--warn { color: #d97706; }
.status--info { color: #0f172a; }
.status-sub { display: block; margin-top: 8rpx; font-size: 24rpx; color: #64748b; }
.btn-pay, .btn-cancel { margin-top: 16rpx; border-radius: 16rpx; font-size: 30rpx; }
.btn-pay { background: #73b054; color: #fff; }
.btn-cancel { background: #fff; color: #64748b; border: 1rpx solid #e2e8f0; }
.state { padding: 80rpx; text-align: center; color: #64748b; }
.state--err { color: #dc2626; }
.tail { height: 40rpx; }
</style>
