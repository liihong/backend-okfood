<template>
  <view class="page">
    <OkNavbar show-back title="开卡订单详情" />
    <scroll-view scroll-y class="scroll" :show-scrollbar="false">
      <view v-if="loading" class="state-text">加载中…</view>
      <view v-else-if="loadError" class="state-text state-text--err">{{ loadError }}</view>
      <view v-else-if="order" class="body">
        <view class="card">
          <view class="row row--head">
            <text class="label">状态</text>
            <text :class="['status-main', `status-main--${statusTone}`]">{{ statusLine }}</text>
          </view>
          <text v-if="statusSub" class="status-sub">{{ statusSub }}</text>
        </view>

        <view class="card">
          <text class="card-title">方案与金额</text>
          <view class="row">
            <text class="label">方案</text>
            <text class="value value--strong">{{ orderTitle }}</text>
          </view>
          <view v-if="order.card_kind" class="row">
            <text class="label">卡型</text>
            <text class="value">{{ order.card_kind }}</text>
          </view>
          <view v-if="order.original_amount_yuan && order.coupon_discount_yuan" class="row">
            <text class="label">原价</text>
            <text class="value value--orig">¥ {{ order.original_amount_yuan }}</text>
          </view>
          <view v-if="order.coupon_discount_yuan" class="row">
            <text class="label">优惠券</text>
            <text class="value value--save">-¥ {{ order.coupon_discount_yuan }}</text>
          </view>
          <view class="row">
            <text class="label">应付</text>
            <text class="value value--amt">¥ {{ order.amount_yuan || '0.00' }}</text>
          </view>
        </view>

        <view class="card">
          <text class="card-title">配送信息</text>
          <view class="row">
            <text class="label">起送日</text>
            <text class="value">{{ order.delivery_start_date || '支付后完善' }}</text>
          </view>
        </view>

        <view class="card">
          <text class="card-title">订单信息</text>
          <view class="row">
            <text class="label">订单号</text>
            <text class="value">#{{ order.id }}</text>
          </view>
          <view class="row">
            <text class="label">商户单号</text>
            <text class="value value--mono">{{ order.out_trade_no || '—' }}</text>
          </view>
          <view class="row">
            <text class="label">下单时间</text>
            <text class="value">{{ createdAtText }}</text>
          </view>
        </view>

        <button
          v-if="isPendingPay"
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
import { getMemberToken, request } from '@/utils/api.js'
import { getMemberCardOrder } from '@/utils/memberCardOrderApi.js'
import { payMemberCardOrderWechat } from '@/utils/memberCardPay.js'
import { shouldOpenMemberSetup } from '@/utils/memberProfile.js'
import { markMinePageNeedsRefresh } from '@/utils/minePageRefresh.js'

const orderId = ref(0)
const order = ref(null)
const loading = ref(true)
const loadError = ref('')
const paying = ref(false)

const isPendingPay = computed(() => String(order.value?.pay_status || '') === '未缴')

const orderTitle = computed(() => {
  const r = order.value?.remark
  if (r && String(r).length > 0) {
    return String(r).replace(/^卡包模版#\d+·/, '卡包 · ')
  }
  const k = order.value?.card_kind || '会员'
  return `${k} · 开卡订单`
})

const statusLine = computed(() => {
  const ps = String(order.value?.pay_status || '')
  if (ps === '未缴') return '待支付'
  if (ps === '已缴') return '已支付'
  return ps || '—'
})

const statusTone = computed(() => {
  const ps = String(order.value?.pay_status || '')
  if (ps === '未缴') return 'warn'
  if (ps === '已缴') return 'ok'
  return 'info'
})

const statusSub = computed(() => {
  if (!isPendingPay.value) return ''
  return '请完成支付；支付成功后将引导您完善配送信息。'
})

const createdAtText = computed(() => {
  const ca = order.value?.created_at
  if (!ca) return '—'
  const s = String(ca)
  return s.length >= 16 ? s.slice(0, 16).replace('T', ' ') : s
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
    const data = await getMemberCardOrder(orderId.value)
    order.value = data && typeof data === 'object' ? data : null
    if (!order.value) loadError.value = '订单数据异常'
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

/** 支付成功后：续卡回「我的」，新用户去完善配送信息 */
async function afterPaySuccess(paySynced) {
  markMinePageNeedsRefresh()
  let preProfile = null
  try {
    preProfile = await request('/api/user/me', { method: 'GET', retry: 0 })
  } catch {
    preProfile = null
  }
  const balBefore = Math.max(0, Math.floor(Number(preProfile?.balance) || 0))
  const activeRenewal =
    balBefore > 0 &&
    preProfile &&
    typeof preProfile === 'object' &&
    !shouldOpenMemberSetup(preProfile)

  if (activeRenewal) {
    uni.showToast({
      title: paySynced ? '支付成功' : '支付已提交，状态同步中',
      icon: 'success',
    })
    setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
    return
  }

  if (paySynced) {
    uni.showToast({ title: '支付成功', icon: 'success' })
  } else {
    uni.showModal({
      title: '支付已提交',
      content:
        '微信已扣款，订单状态正在同步。请先完善配送信息；若后台长时间仍显示未缴，请联系客服核对。',
      showCancel: false,
    })
  }
  setTimeout(() => {
    uni.redirectTo({
      url: '/packageUser/pages/memberSetup/memberSetup?from=pay',
    })
  }, paySynced ? 400 : 80)
}

async function continuePay() {
  if (!order.value || paying.value || !isPendingPay.value) return
  paying.value = true
  uni.showLoading({ title: '拉起支付…', mask: true })
  try {
    const payOut = await payMemberCardOrderWechat(order.value.id)
    const paySynced = payOut?.paySynced !== false
    await loadDetail()
    await afterPaySuccess(paySynced)
  } catch (e) {
    const raw = e && typeof e === 'object' ? e : {}
    const errMsg = typeof raw.errMsg === 'string' ? raw.errMsg : ''
    const msg = errMsg || (e instanceof Error ? e.message : '支付未完成')
    if (!String(msg).includes('cancel') && !String(msg).includes('取消')) {
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

.label {
  font-size: 26rpx;
  color: $ok-slate-400;
  font-weight: 800;
  flex-shrink: 0;
}

.value {
  font-size: 26rpx;
  color: $ok-slate-700;
  font-weight: 700;
  text-align: right;
  flex: 1;
}

.value--strong {
  font-weight: 900;
  color: $ok-slate-800;
}

.value--amt {
  font-size: 34rpx;
  font-weight: 950;
  color: $ok-urgent-red;
}

.value--orig {
  text-decoration: line-through;
  color: $ok-slate-400;
}

.value--save {
  color: $ok-emerald;
}

.value--mono {
  font-size: 22rpx;
  word-break: break-all;
}

.status-main {
  font-size: 30rpx;
  font-weight: 950;
}

.status-main--warn {
  color: #b45309;
}

.status-main--ok {
  color: $ok-emerald;
}

.status-main--info {
  color: $ok-slate-600;
}

.status-sub {
  display: block;
  font-size: 24rpx;
  color: $ok-slate-500;
  line-height: 1.45;
}

.btn-pay {
  width: 100%;
  height: 96rpx;
  line-height: 96rpx;
  margin: 8rpx 0 0;
  border-radius: 48rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 30rpx;
  font-weight: 800;
  border: none;
}

.btn-pay[disabled] {
  opacity: 0.55;
}

.btn-pay::after {
  border: none;
}

.tail {
  height: 48rpx;
}
</style>
