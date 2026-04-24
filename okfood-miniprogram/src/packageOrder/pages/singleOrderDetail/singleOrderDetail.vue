<template>
  <view class="page">
    <OkNavbar show-back title="订单详情" />
    <scroll-view scroll-y class="scroll" :show-scrollbar="false">
      <view v-if="loading" class="state-text">加载中…</view>
      <view v-else-if="loadError" class="state-text state-text--err">{{ loadError }}</view>
      <view v-else-if="order" class="body">
        <view class="card">
          <view class="row row--head">
            <text class="label">状态</text>
            <text :class="['status-main', `status-main--${status.tone}`]">{{ status.line1 }}</text>
          </view>
          <text class="status-sub">{{ status.line2 }}</text>
        </view>

        <view class="card">
          <text class="card-title">餐品与金额</text>
          <view class="row">
            <text class="label">餐品</text>
            <text class="value value--strong">{{ order.dish_title || '—' }}</text>
          </view>
          <view class="row">
            <text class="label">份数</text>
            <text class="value">×{{ order.quantity ?? 1 }}</text>
          </view>
          <view class="row">
            <text class="label">供餐日</text>
            <text class="value">{{ order.delivery_date || '—' }}</text>
          </view>
          <view class="row">
            <text class="label">实付</text>
            <text class="value value--amt">¥ {{ order.amount_yuan || '0.00' }}</text>
          </view>
        </view>

        <view class="card">
          <text class="card-title">配送 / 自提</text>
          <view class="row">
            <text class="label">方式</text>
            <text class="value">{{ order.store_pickup ? '门店自提' : '配送到家' }}</text>
          </view>
          <view class="row row--block">
            <text class="label">地址 / 说明</text>
            <text class="value multiline">{{ order.address_summary || '—' }}</text>
          </view>
          <view v-if="!order.store_pickup && order.routing_area" class="row">
            <text class="label">片区</text>
            <text class="value">{{ order.routing_area }}</text>
          </view>
        </view>

        <view class="card">
          <text class="card-title">订单信息</text>
          <view class="row">
            <text class="label">商户单号</text>
            <text class="value value--mono">{{ order.out_trade_no || '—' }}</text>
          </view>
          <view class="row">
            <text class="label">支付</text>
            <text class="value">{{ order.pay_status || '—' }}</text>
          </view>
          <view v-if="order.pay_channel" class="row">
            <text class="label">支付渠道</text>
            <text class="value">{{ order.pay_channel }}</text>
          </view>
          <view class="row">
            <text class="label">履约</text>
            <text class="value">{{ fulfillLabel }}</text>
          </view>
          <view class="row">
            <text class="label">下单时间</text>
            <text class="value">{{ createdAtText }}</text>
          </view>
        </view>

        <button
          v-if="order.pay_status === '未支付'"
          class="btn-pay"
          :disabled="paying"
          hover-class="none"
          @tap="continuePay"
        >
          {{ paying ? '支付中…' : '继续支付' }}
        </button>
        <view class="tail" />
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  fetchWechatJsapiPayParams,
  getSingleMealOrder,
  singleOrderStatusMeta,
} from '@/utils/singleOrderApi.js'
import { getMemberToken } from '@/utils/api.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'

const orderId = ref(0)
const order = ref(null)
const loading = ref(true)
const loadError = ref('')
const paying = ref(false)

const status = computed(() => (order.value ? singleOrderStatusMeta(order.value) : { line1: '', line2: '', tone: 'info' }))

const fulfillLabel = computed(() => {
  const o = order.value
  if (!o) return '—'
  const f = String(o.fulfillment_status || '')
  if (f === 'delivered') return '已完成'
  if (f === 'pending') return '进行中'
  return f || '—'
})

const createdAtText = computed(() => {
  const raw = order.value?.created_at
  if (raw == null || raw === '') return '—'
  const s = typeof raw === 'string' ? raw : String(raw)
  return s.replace('T', ' ').replace(/\.\d+Z?$/, '').slice(0, 19)
})

onLoad((options) => {
  const raw = options?.id || options?.order_id || options?.orderId || ''
  const id = raw ? parseInt(String(decodeURIComponent(raw)), 10) : NaN
  if (!Number.isFinite(id) || id < 1) {
    loading.value = false
    loadError.value = '缺少订单编号'
    return
  }
  orderId.value = id
  void loadDetail()
})

async function loadDetail() {
  if (!getMemberToken()) {
    loading.value = false
    loadError.value = '请先登录'
    return
  }
  loading.value = true
  loadError.value = ''
  order.value = null
  try {
    const data = await getSingleMealOrder(orderId.value)
    order.value = data && typeof data === 'object' ? data : null
    if (!order.value) loadError.value = '订单数据异常'
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function continuePay() {
  if (!order.value || paying.value) return
  if (order.value.pay_status !== '未支付') return
  paying.value = true
  uni.showLoading({ title: '拉起支付…', mask: true })
  try {
    await syncWxMiniOpenidFromLogin()
    const pay = await fetchWechatJsapiPayParams(order.value.id)
    await new Promise((resolve, reject) => {
      uni.requestPayment({
        provider: 'wxpay',
        timeStamp: String(pay.timeStamp),
        nonceStr: pay.nonceStr,
        package: pay.package,
        signType: pay.signType || 'MD5',
        paySign: pay.paySign,
        success: resolve,
        fail: reject,
      })
    })
    uni.showToast({ title: '支付成功', icon: 'success' })
    await loadDetail()
  } catch (e) {
    const msg =
      e && typeof e === 'object' && 'errMsg' in e && typeof e.errMsg === 'string'
        ? e.errMsg
        : e instanceof Error
          ? e.message
          : '支付未完成'
    if (!String(msg).includes('cancel')) {
      uni.showToast({ title: msg, icon: 'none' })
    }
  } finally {
    paying.value = false
    uni.hideLoading()
  }
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

.state-text {
  padding: 80rpx 40rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.state-text--err {
  color: #b91c1c;
}

.body {
  padding: 24rpx 40rpx;
}

.card {
  background: #fff;
  border-radius: 48rpx;
  padding: 32rpx 36rpx;
  margin-bottom: 24rpx;
  border: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.04);
}

.card-title {
  display: block;
  font-size: 26rpx;
  font-weight: 950;
  color: $ok-slate-400;
  margin-bottom: 20rpx;
}

.row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24rpx;
  margin-bottom: 16rpx;
}

.row:last-child {
  margin-bottom: 0;
}

.row--head {
  margin-bottom: 8rpx;
  align-items: center;
}

.row--block {
  flex-direction: column;
}

.label {
  font-size: 26rpx;
  color: $ok-slate-400;
  font-weight: 800;
  flex-shrink: 0;
}

.value {
  font-size: 26rpx;
  color: #333;
  font-weight: 800;
  text-align: right;
  flex: 1;
  min-width: 0;
}

.value--strong {
  font-weight: 950;
  font-size: 28rpx;
}

.value--amt {
  font-size: 32rpx;
  color: $ok-forest-green;
  font-weight: 950;
}

.value--mono {
  font-family: ui-monospace, monospace;
  font-size: 24rpx;
  word-break: break-all;
}

.multiline {
  text-align: left;
  line-height: 1.45;
}

.status-main {
  font-size: 30rpx;
  font-weight: 950;
}

.status-main--warn {
  color: #c2410c;
}

.status-main--ok {
  color: #047857;
}

.status-main--info {
  color: #1d4ed8;
}

.status-sub {
  display: block;
  font-size: 24rpx;
  color: $ok-slate-500;
  font-weight: 700;
  line-height: 1.4;
}

.btn-pay {
  width: 100%;
  margin-top: 8rpx;
  background: $ok-sunshine-yellow;
  color: $ok-forest-green;
  padding: 36rpx;
  border-radius: 60rpx;
  font-weight: 950;
  font-size: 32rpx;
  box-shadow: 0 20rpx 50rpx rgba(250, 204, 21, 0.3);
  border: none;
  line-height: 1.35;
}

.btn-pay::after {
  border: none;
}

.tail {
  height: calc(32rpx + env(safe-area-inset-bottom));
}
</style>
