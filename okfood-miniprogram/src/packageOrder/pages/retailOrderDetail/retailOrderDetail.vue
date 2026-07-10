<template>
  <view class="page">
    <OkNavbar show-back title="商城订单详情" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view v-if="loading" class="state">加载中…</view>
      <view v-else-if="loadError" class="state state--err">{{ loadError }}</view>
      <view v-else-if="order" class="body">
        <RetailOrderDetailCard>
          <text class="status" :class="`status--${status.tone}`">{{ status.line1 }}</text>
          <text class="status-sub">{{ status.line2 }}</text>
        </RetailOrderDetailCard>

        <RetailOrderDetailCard>
          <RetailOrderDetailRow label="商品" :value="order.product_title" />
          <RetailOrderDetailRow label="数量" :value="`×${order.quantity}`" />
          <RetailOrderDetailRow label="金额" :value="`¥ ${order.amount_yuan}`" value-class="amt" />
        </RetailOrderDetailCard>

        <RetailOrderDetailCard>
          <RetailOrderDetailRow
            label="方式"
            :value="order.store_pickup ? '门店自提' : '配送到家'"
          />
          <RetailOrderDetailRow
            label="地址"
            :value="order.address_summary || '—'"
            block
          >
            <template v-if="canModifyAddress" #action>
              <text class="link-btn" @tap="openAddressSheet">修改</text>
            </template>
          </RetailOrderDetailRow>
        </RetailOrderDetailCard>

        <RetailOrderDetailCard>
          <RetailOrderDetailRow label="单号" :value="order.out_trade_no" value-class="mono" />
          <RetailOrderDetailRow label="下单" :value="createdAtText" />
        </RetailOrderDetailCard>

        <button
          v-if="order.pay_status === '未支付' && order.fulfillment_status === 'pending'"
          class="btn-pay"
          :disabled="paying"
          @tap="continuePay"
        >
          {{ paying ? '处理中…' : '继续支付' }}
        </button>

        <view v-if="showAwaitingAcceptActions" class="action-row">
          <button
            v-if="canCancel"
            class="btn-action btn-action--ghost"
            :disabled="cancelling"
            hover-class="none"
            @tap="onCancel"
          >
            {{ cancelling ? '取消中…' : '取消订单' }}
          </button>
          <button
            v-if="canModifyAddress"
            class="btn-action btn-action--primary"
            hover-class="none"
            @tap="openAddressSheet"
          >
            修改地址
          </button>
        </view>

        <button
          v-else-if="canCancel"
          class="btn-cancel"
          :disabled="cancelling"
          @tap="onCancel"
        >
          {{ cancelling ? '取消中…' : '取消订单' }}
        </button>

        <view class="tail" />
      </view>
    </scroll-view>

    <MemberAddressSelectSheet
      :visible="addressSheetVisible"
      :selected-address-id="order?.member_address_id"
      title="修改配送地址"
      confirm-text="确认修改"
      @close="addressSheetVisible = false"
      @confirm="onAddressConfirm"
    />
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import RetailOrderDetailCard from '@/components/RetailOrderDetailCard/RetailOrderDetailCard.vue'
import RetailOrderDetailRow from '@/components/RetailOrderDetailRow/RetailOrderDetailRow.vue'
import MemberAddressSelectSheet from '@/components/MemberAddressSelectSheet/MemberAddressSelectSheet.vue'
import { getPageScrollStyle } from '@/utils/navbar.js'
import { getMemberToken } from '@/utils/api.js'
import {
  canCancelRetailOrder,
  canModifyRetailOrderAddress,
  cancelRetailOrder,
  formatRetailOrderCreatedAt,
  getRetailOrder,
  retailOrderStatusMeta,
  updateRetailOrderDeliveryAddress,
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
const addressSheetVisible = ref(false)

const status = computed(() => retailOrderStatusMeta(order.value || {}))
const createdAtText = computed(() => formatRetailOrderCreatedAt(order.value?.created_at))
const canCancel = computed(() => canCancelRetailOrder(order.value))
const canModifyAddress = computed(() => canModifyRetailOrderAddress(order.value))
const showAwaitingAcceptActions = computed(() => {
  if (!order.value) return false
  return (
    String(order.value.pay_status || '').trim() === '已支付' &&
    String(order.value.fulfillment_status || '').trim().toLowerCase() === 'awaiting_accept'
  )
})

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

function openAddressSheet() {
  if (!canModifyAddress.value) return
  addressSheetVisible.value = true
}

async function onAddressConfirm(payload) {
  const finish = typeof payload?.finish === 'function' ? payload.finish : () => {}
  const memberAddressId = Number(payload?.memberAddressId)
  if (!Number.isFinite(memberAddressId) || memberAddressId < 1) {
    finish()
    return
  }
  try {
    const data = await updateRetailOrderDeliveryAddress(orderId.value, memberAddressId)
    order.value = data && typeof data === 'object' ? data : order.value
    addressSheetVisible.value = false
    uni.showToast({ title: '地址已更新', icon: 'success' })
    await loadOrder()
  } catch (e) {
    uni.showToast({ title: e instanceof Error ? e.message : '修改失败', icon: 'none' })
  } finally {
    finish()
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
  const paid = order.value?.pay_status === '已支付'
  showOkAlert({
    title: '取消订单',
    content: paid
      ? '确定取消该商城订单？支付金额将原路退回至您的微信账户。'
      : '确定取消该商城订单？',
    tone: paid ? 'warning' : 'default',
    confirmText: paid ? '确定取消' : '确定',
    confirmColor: paid ? '#b91c1c' : undefined,
    success: async (res) => {
      if (!res.confirm) return
      cancelling.value = true
      uni.showLoading({ title: '处理中…', mask: true })
      try {
        const data = await cancelRetailOrder(orderId.value)
        order.value = data && typeof data === 'object' ? data : order.value
        await loadOrder()
        uni.showToast({
          title: paid ? '已取消，款项将原路退回' : '已取消',
          icon: 'success',
        })
      } catch (e) {
        uni.showToast({ title: e instanceof Error ? e.message : '取消失败', icon: 'none' })
      } finally {
        cancelling.value = false
        uni.hideLoading()
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
.status { font-size: 34rpx; font-weight: 800; display: block; }
.status--ok { color: #16a34a; }
.status--warn { color: #d97706; }
.status--info { color: #0f172a; }
.status-sub { display: block; margin-top: 8rpx; font-size: 24rpx; color: #64748b; }
:deep(.amt) { color: #73b054; font-weight: 800; }
:deep(.mono) { font-family: monospace; font-size: 24rpx; }
.link-btn {
  flex-shrink: 0;
  font-size: 26rpx;
  color: #73b054;
  font-weight: 800;
}
.btn-pay, .btn-cancel { margin-top: 16rpx; border-radius: 16rpx; font-size: 30rpx; }
.btn-pay { background: #73b054; color: #fff; }
.btn-cancel { background: #fff; color: #64748b; border: 1rpx solid #e2e8f0; }
.action-row {
  display: flex;
  gap: 20rpx;
  margin-top: 16rpx;
}
.btn-action {
  flex: 1;
  margin: 0;
  border-radius: 16rpx;
  font-size: 30rpx;
  line-height: 1.35;
  padding: 28rpx 16rpx;
}
.btn-action::after { border: none; }
.btn-action--ghost {
  background: #fff;
  color: #b91c1c;
  border: 1rpx solid rgba(185, 28, 28, 0.35);
}
.btn-action--primary {
  background: #73b054;
  color: #fff;
  border: none;
}
.btn-action[disabled] { opacity: 0.55; }
.state { padding: 80rpx; text-align: center; color: #64748b; }
.state--err { color: #dc2626; }
.tail { height: 40rpx; }
</style>
