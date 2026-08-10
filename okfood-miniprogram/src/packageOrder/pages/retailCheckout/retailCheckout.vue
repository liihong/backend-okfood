<template>
  <view class="page">
    <OkNavbar show-back title="购物车结算" />
    <view v-if="loading" class="state">加载中…</view>
    <view v-else-if="loadError" class="state state--err">{{ loadError }}</view>
    <scroll-view v-else scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="body">
        <!-- 配送地址：默认只展示当前选中一条，右侧切换 -->
        <view class="card addr-card">
          <view class="addr-head">
            <text class="card-label card-label--inline">配送地址</text>
            <text
              class="addr-switch"
              @tap="addressRows.length ? openAddressSheet() : goAddressList()"
            >
              {{ addressRows.length ? '切换' : '去添加' }}
            </text>
          </view>
          <view v-if="!selectedAddress" class="addr-empty">
            <text class="addr-empty-txt">暂无地址，请先添加配送地址</text>
            <button class="btn-ghost" hover-class="none" @tap="goAddressList">添加地址</button>
          </view>
          <view v-else class="addr-selected" @tap="openAddressSheet">
            <view class="addr-selected-main">
              <view class="addr-line1">
                <text class="addr-name">{{ selectedAddress.name }}</text>
                <text class="addr-phone">{{ selectedAddress.phone }}</text>
                <text v-if="selectedAddress.isDefault" class="addr-badge">默认</text>
              </view>
              <text class="addr-line2">{{ selectedAddress.line }}</text>
            </view>
            <text class="addr-chevron">›</text>
          </view>
        </view>

        <view class="card">
          <text class="card-label">商品明细（{{ cartItems.length }} 种）</text>
          <RetailCartLineItem
            v-for="it in cartItems"
            :key="it.retailProductId"
            :item="it"
            @inc="() => onInc(it)"
            @dec="() => onDec(it)"
          />
        </view>

        <view v-if="availableCoupons.length" class="card">
          <text class="card-label">优惠券</text>
          <picker :range="couponLabels" @change="onCouponPick">
            <view class="coupon-pick">
              <text class="coupon-pick-txt">{{ selectedCouponLabel }}</text>
              <text class="coupon-pick-arrow">›</text>
            </view>
          </picker>
        </view>

        <view class="card sum-card">
          <view class="sum-row"><text>商品小计</text><text>¥ {{ subtotalText }}</text></view>
          <view v-if="couponSaveText" class="sum-row sum-row--disc">
            <text>优惠券</text><text>- ¥ {{ couponSaveText }}</text>
          </view>
          <view class="sum-row sum-row--total">
            <text>合计</text><text class="sum-amt">¥ {{ payableText }}</text>
          </view>
        </view>
      </view>
    </scroll-view>

    <view v-if="!loading && !loadError" class="footer">
      <button class="pay-btn" :disabled="!!payBlockReason || paying" @tap="onPay">
        {{ paying ? '处理中…' : `支付 ¥ ${payableText}` }}
      </button>
    </view>

    <MemberAddressSelectSheet
      :visible="addressSheetVisible"
      :selected-address-id="selectedAddressId"
      title="选择配送地址"
      confirm-text="确认选择"
      @close="addressSheetVisible = false"
      @confirm="onAddressConfirm"
    />
  </view>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { onLoad, onShow, onReady } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import RetailCartLineItem from '@/components/RetailCart/RetailCartLineItem.vue'
import MemberAddressSelectSheet from '@/components/MemberAddressSelectSheet/MemberAddressSelectSheet.vue'
import {
  getPageScrollStyle,
  schedulePageScrollLayout,
  FIXED_FOOTER_RESERVE_PX,
} from '@/utils/navbar.js'
import { getMemberToken, request } from '@/utils/api.js'
import { fetchStoreInfo } from '@/utils/catalogApi.js'
import {
  normalizeAddressList,
  sortAddressesDefaultFirst,
  getAddressRecordId,
  addressListRow,
} from '@/utils/addressApi.js'
import { createRetailOrder } from '@/utils/retailOrder/retailOrderApi.js'
import { payRetailOrderWechat } from '@/utils/retailOrder/retailOrderPay.js'
import { listAvailableMemberCoupons } from '@/utils/memberCouponApi.js'
import { promptUnpaidOrderConflict } from '@/utils/unpaidOrderPrompt.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'
import { showOkAlert } from '@/utils/okAlert.js'
import { syncCartWithRetailMenu } from '@/utils/retailCart/retailCartSync.js'
import {
  addCartItem,
  setCartItemQuantity,
  clearCart,
  getCartSubtotalText,
} from '@/utils/retailCart/retailCartStorage.js'
import { notifyRetailCartChanged } from '@/utils/retailCart/useRetailCart.js'

const scrollStyle = ref(getPageScrollStyle(0, FIXED_FOOTER_RESERVE_PX))
const cartItems = ref([])
const loading = ref(true)
const loadError = ref('')
const paying = ref(false)
const addressRows = ref([])
const rawAddresses = ref([])
const selectedIndex = ref(0)
const addressSheetVisible = ref(false)
const availableCoupons = ref([])
const selectedCouponId = ref(null)

const selectedAddress = computed(() => addressRows.value[selectedIndex.value] || null)
const selectedAddressId = computed(() => selectedAddress.value?.id || '')

const subtotalText = computed(() => getCartSubtotalText())
const selectedCoupon = computed(() =>
  availableCoupons.value.find((c) => Number(c.id) === Number(selectedCouponId.value)) || null,
)
const couponSaveText = computed(() => {
  const n = Number(selectedCoupon.value?.discount_yuan)
  return Number.isFinite(n) && n > 0 ? n.toFixed(2) : null
})
const payableText = computed(() => {
  const base = Number(subtotalText.value)
  const disc = couponSaveText.value ? Number(couponSaveText.value) : 0
  return Math.max(0.01, base - disc).toFixed(2)
})
const couponLabels = computed(() => [
  '不使用优惠券',
  ...availableCoupons.value.map((c) => `${c.template_name || '优惠券'} -¥${c.discount_yuan}`),
])
const selectedCouponLabel = computed(() => {
  if (selectedCouponId.value == null) return '不使用优惠券'
  const c = selectedCoupon.value
  return c ? `${c.template_name || '优惠券'} -¥${c.discount_yuan}` : '不使用优惠券'
})
const payBlockReason = computed(() => {
  if (paying.value) return ''
  if (!cartItems.value.length) return '购物车为空'
  if (!addressRows.value.length) return '请先添加配送地址'
  if (!getAddressRecordId(rawAddresses.value[selectedIndex.value])) return '请选择有效地址'
  return ''
})

function applyScrollLayout() {
  schedulePageScrollLayout((style) => {
    scrollStyle.value = style
  }, FIXED_FOOTER_RESERVE_PX)
}

/**
 * 写入地址列表；优先保留当前已选地址 id，避免 onShow 刷新后跳回默认项
 * @param {unknown} raw
 * @param {string|number|null} [preferredId]
 */
function applyAddressList(raw, preferredId = null) {
  const prevId =
    preferredId != null && preferredId !== ''
      ? String(preferredId)
      : getAddressRecordId(rawAddresses.value[selectedIndex.value])
  const list = sortAddressesDefaultFirst(normalizeAddressList(raw))
  rawAddresses.value = list
  addressRows.value = list.map((item, i) => addressListRow(item, i))
  if (prevId) {
    const idx = list.findIndex((item) => String(getAddressRecordId(item)) === prevId)
    selectedIndex.value = idx >= 0 ? idx : 0
  } else {
    selectedIndex.value = 0
  }
}

function retailItemsPayload() {
  return cartItems.value.map((it) => ({
    retail_product_id: Number(it.retailProductId),
    quantity: Math.max(1, Number(it.quantity) || 1),
  }))
}

async function loadCoupons() {
  if (!cartItems.value.length) return
  try {
    const list = await listAvailableMemberCoupons({
      biz_type: 'store_retail',
      retail_items: retailItemsPayload(),
      store_pickup: false,
    })
    availableCoupons.value = Array.isArray(list) ? list : []
  } catch {
    availableCoupons.value = []
  }
}

async function loadPage() {
  loading.value = true
  loadError.value = ''
  try {
    const { items, removed } = await syncCartWithRetailMenu()
    if (removed.length) {
      uni.showToast({ title: `${removed[0]}等已失效`, icon: 'none' })
    }
    if (!items.length) throw new Error('购物车为空，请返回加点商品')
    cartItems.value = items
    await fetchStoreInfo().catch(() => null)
    applyAddressList(await request('/api/user/me/addresses', { method: 'GET', retry: 1 }), null)
    selectedIndex.value = 0
    await loadCoupons()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
    nextTick(() => applyScrollLayout())
  }
}

function goAddressList() {
  uni.navigateTo({ url: '/packageUser/pages/address/list' })
}

function openAddressSheet() {
  if (!addressRows.value.length) {
    goAddressList()
    return
  }
  addressSheetVisible.value = true
}

/** 弹层确认：刷新地址列表并选中目标项 */
async function onAddressConfirm(payload) {
  const finish = typeof payload?.finish === 'function' ? payload.finish : () => {}
  const memberAddressId = Number(payload?.memberAddressId)
  try {
    if (!Number.isFinite(memberAddressId) || memberAddressId < 1) {
      uni.showToast({ title: '地址无效，请重新选择', icon: 'none' })
      return
    }
    try {
      const raw = await request('/api/user/me/addresses', { method: 'GET', retry: 1 })
      applyAddressList(raw, memberAddressId)
    } catch {
      const idx = rawAddresses.value.findIndex(
        (item) => String(getAddressRecordId(item)) === String(memberAddressId),
      )
      if (idx >= 0) selectedIndex.value = idx
    }
    addressSheetVisible.value = false
  } finally {
    finish()
  }
}

function onInc(it) {
  addCartItem(it, 1)
  notifyRetailCartChanged()
  void syncCartWithRetailMenu().then(({ items }) => {
    cartItems.value = items
    void loadCoupons()
  })
}

function onDec(it) {
  setCartItemQuantity(it.retailProductId, (Number(it.quantity) || 1) - 1)
  notifyRetailCartChanged()
  void syncCartWithRetailMenu().then(({ items }) => {
    cartItems.value = items
    if (!items.length) loadError.value = '购物车为空'
    void loadCoupons()
  })
}

function onCouponPick(e) {
  const idx = Number(e?.detail?.value)
  if (idx <= 0) selectedCouponId.value = null
  else selectedCouponId.value = availableCoupons.value[idx - 1]?.id ?? null
}

async function onPay() {
  if (payBlockReason.value) {
    uni.showToast({ title: payBlockReason.value, icon: 'none' })
    return
  }
  paying.value = true
  uni.showLoading({ title: '创建订单…', mask: true })
  try {
    await syncWxMiniOpenidFromLogin()
    const addrId = getAddressRecordId(rawAddresses.value[selectedIndex.value])
    const payload = {
      items: retailItemsPayload(),
      store_pickup: false,
      member_address_id: Number(addrId),
    }
    if (selectedCouponId.value != null) {
      payload.member_coupon_id = Math.floor(Number(selectedCouponId.value))
    }
    const out = await createRetailOrder(payload)
    const orderId = out?.id
    if (orderId == null) throw new Error('订单创建响应异常')
    uni.showLoading({ title: '拉起支付…', mask: true })
    await payRetailOrderWechat(orderId)
    clearCart()
    notifyRetailCartChanged()
    showOkAlert({
      title: '支付成功',
      content: '您的商城订单已提交',
      tone: 'success',
      showCancel: false,
      success: () => {
        uni.setStorageSync('okfood_open_orders_tab', 'retail')
        uni.switchTab({ url: '/pages/orders/index' })
      },
    })
  } catch (e) {
    if (promptUnpaidOrderConflict(e, { kind: 'retail' })) return
    uni.showToast({ title: e instanceof Error ? e.message : '支付失败', icon: 'none' })
  } finally {
    paying.value = false
    uni.hideLoading()
  }
}

onReady(applyScrollLayout)
onLoad(() => {
  applyScrollLayout()
  if (!getMemberToken()) {
    loading.value = false
    loadError.value = '请先登录'
    return
  }
  void loadPage()
})
onShow(() => {
  applyScrollLayout()
  if (!getMemberToken()) return
  void request('/api/user/me/addresses', { method: 'GET', retry: 1 })
    .then((raw) => applyAddressList(raw))
    .catch(() => {})
})
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: $ok-slate-50;
}

.scroll {
  flex: 1;
  min-height: 0;
}

.body {
  padding: 24rpx 28rpx 32rpx;
  padding-bottom: 160rpx;
}

.card {
  background: #fff;
  border-radius: 24rpx;
  padding: 28rpx 28rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 20rpx rgba(15, 23, 42, 0.04);
}

.card-label {
  font-size: 24rpx;
  font-weight: 800;
  color: #94a3b8;
  margin-bottom: 16rpx;
  display: block;
}

.card-label--inline {
  margin-bottom: 0;
  font-size: 28rpx;
  color: #0f172a;
}

.state {
  padding: 80rpx 32rpx;
  text-align: center;
  color: #64748b;
}

.state--err {
  color: #dc2626;
}

/* —— 地址卡片 —— */
.addr-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
}

.addr-switch {
  font-size: 26rpx;
  font-weight: 700;
  color: #73b054;
  padding: 8rpx 4rpx 8rpx 16rpx;
}

.addr-empty {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  align-items: flex-start;
}

.addr-empty-txt {
  color: #64748b;
  font-size: 26rpx;
}

.btn-ghost {
  margin: 0;
  font-size: 26rpx;
  font-weight: 700;
  color: #73b054;
  background: rgba(115, 176, 84, 0.1);
  border-radius: 12rpx;
  padding: 14rpx 28rpx;
  line-height: 1.3;
}

.btn-ghost::after {
  border: none;
}

.addr-selected {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 20rpx 22rpx;
  background: #f8fafc;
  border-radius: 16rpx;
}

.addr-selected:active {
  background: rgba(115, 176, 84, 0.08);
}

.addr-selected-main {
  flex: 1;
  min-width: 0;
}

.addr-line1 {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.addr-name,
.addr-phone {
  font-size: 30rpx;
  font-weight: 800;
  color: #0f172a;
}

.addr-badge {
  padding: 2rpx 12rpx;
  border-radius: 999rpx;
  background: rgba(115, 176, 84, 0.12);
  color: #73b054;
  font-size: 20rpx;
  font-weight: 700;
}

.addr-line2 {
  display: block;
  font-size: 26rpx;
  color: #64748b;
  line-height: 1.45;
}

.addr-chevron {
  flex-shrink: 0;
  font-size: 36rpx;
  color: #cbd5e1;
  font-weight: 300;
  line-height: 1;
}

.coupon-pick {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 22rpx;
  background: #f8fafc;
  border-radius: 14rpx;
}

.coupon-pick-txt {
  font-size: 26rpx;
  color: #334155;
  font-weight: 600;
}

.coupon-pick-arrow {
  font-size: 32rpx;
  color: #cbd5e1;
}

.sum-row {
  display: flex;
  justify-content: space-between;
  padding: 10rpx 0;
  font-size: 26rpx;
  color: #64748b;
}

.sum-row--disc {
  color: #ea580c;
}

.sum-row--total {
  margin-top: 12rpx;
  padding-top: 18rpx;
  border-top: 1rpx solid #f1f5f9;
  font-size: 30rpx;
  font-weight: 800;
  color: #0f172a;
}

.sum-amt {
  color: #ea580c;
  font-weight: 900;
}

.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 16rpx 28rpx calc(16rpx + env(safe-area-inset-bottom));
  background: #fff;
  box-shadow: 0 -4rpx 24rpx rgba(15, 23, 42, 0.06);
}

.pay-btn {
  margin: 0;
  background: linear-gradient(135deg, #f59e0b, #ea580c);
  color: #fff;
  border-radius: 999rpx;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 1.35;
  padding: 26rpx 16rpx;
}

.pay-btn::after {
  border: none;
}

.pay-btn[disabled] {
  opacity: 0.5;
}
</style>
