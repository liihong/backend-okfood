<template>
  <view class="page">
    <OkNavbar show-back title="确认订单" />
    <view v-if="loading" class="state">加载中…</view>
    <view v-else-if="loadError" class="state state--err">{{ loadError }}</view>
    <scroll-view v-else scroll-y class="scroll" :show-scrollbar="false" :style="scrollStyle">
      <view class="body">
        <view v-if="dish" class="card dish-card">
          <text class="card-label">餐品</text>
          <view class="dish-name-row">
            <text class="dish-name">{{ dish.name }}</text>
            <view class="dish-price-col">
              <text v-if="unitPrice != null" class="dish-price">¥ {{ unitPrice }} / 份</text>
              <text v-else class="dish-price dish-price--muted">待公布</text>
            </view>
          </view>
          <view class="dish-meta">
            <text class="meta-tag">{{ dish.day }} · {{ serviceDateYmd }}</text>
          </view>
          <view v-if="dish && dish.singleStockLimited" class="stock-row">
            <text>剩余可单点</text>
            <text class="stock-row-num">{{ dish.singleStockRemaining ?? 0 }}</text>
            <text> 份</text>
          </view>
          <view v-if="unitPrice != null" class="dish-total-row">
            <view class="dish-total-left">
              <text class="dish-total-label">小计</text>
              <view class="qty-inline" @tap.stop>
                <button type="button" class="qty-btn qty-btn--sm" @tap="decQty">−</button>
                <text class="qty-num qty-num--sm">{{ quantity }}</text>
                <button type="button" class="qty-btn qty-btn--sm" @tap="incQty">+</button>
              </view>
              <text class="dish-total-unit-hint">份</text>
            </view>
            <text class="dish-total-amt">¥ {{ totalPriceText }}</text>
          </view>
        </view>

      <view class="card mode-card">
          <text class="card-label">取餐方式</text>
          <radio-group class="mode-group mode-group--row" @change="onFulfillModeChange">
            <label class="mode-row">
              <radio value="delivery" :checked="fulfillMode === 'delivery'" color="#0e5a44" />
              <text class="mode-label">配送到家</text>
            </label>
            <label class="mode-row">
              <radio value="pickup" :checked="fulfillMode === 'pickup'" color="#0e5a44" />
              <text class="mode-label">门店自提</text>
            </label>
          </radio-group>
        </view>

        <view v-if="fulfillMode === 'delivery'" class="card addr-card">
          <view class="addr-head">
            <text class="card-label">配送地址</text>
            <text class="addr-manage" @tap="goAddressList">管理地址</text>
          </view>
          <view v-if="!addressRows.length" class="addr-empty">
            <text>暂无地址，请先添加</text>
            <button class="btn-ghost" @tap="goAddressList">去添加</button>
          </view>
          <view v-else class="addr-list">
            <view
              v-for="(row, i) in addressRows"
              :key="row.id || i"
              class="addr-row"
              :class="{ 'addr-row--on': selectedIndex === i }"
              @tap="selectedIndex = i"
            >
              <view class="addr-radio">
                <view v-if="selectedIndex === i" class="addr-dot-fill" />
                <view v-else class="addr-ring" />
              </view>
              <view class="addr-body">
                <view class="addr-line1">
                  <text class="addr-name">{{ row.name }}</text>
                  <text class="addr-phone">{{ row.phone }}</text>
                  <text v-if="row.isDefault" class="addr-badge">默认</text>
                </view>
                <text class="addr-line2">{{ row.line }}</text>
              </view>
            </view>
          </view>
        </view>

        <view class="hint-box">
          <text class="hint-title">支付说明</text>
          <text class="hint-text">
           <template v-if="fulfillMode === 'delivery'">
              点击「去支付」将调起微信支付。支付成功后，系统会按配送片区派单给骑手。
            </template>
            <template v-else>
              门店自提：支付成功后订单即完成，请按供餐日到店取餐（无需骑手配送）。
            </template>
          </text>
        </view>

        <button
          class="btn-pay"
          :disabled="!canPay || paying"
          :class="{ 'btn-pay--disabled': !canPay || paying }"
          @tap="handlePay"
        >
          {{ paying ? '处理中…' : '去支付' }}
        </button>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  fetchMenuDetail,
  formatMenuPrice,
  isSingleOrderServiceDate,
  singleOrderServiceDateError,
} from '@/utils/menuApi.js'
import { getNavbarLayout } from '@/utils/navbar.js'
import { getMemberToken, request } from '@/utils/api.js'
import {
  normalizeAddressList,
  sortAddressesDefaultFirst,
  getAddressRecordId,
  addressListRow,
} from '@/utils/addressApi.js'
import { createSingleMealOrder, fetchWechatJsapiPayParams } from '@/utils/singleOrderApi.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'

const dish = ref(null)
const loading = ref(true)
const loadError = ref('')
const serviceDateYmd = ref('')
const dishIdStr = ref('')
const addressRows = ref([])
const rawAddresses = ref([])
const selectedIndex = ref(0)
const paying = ref(false)
const scrollStyle = ref({ height: '400px' })
/** delivery | pickup */
const fulfillMode = ref('delivery')
const quantity = ref(1)
const QTY_MAX = 50

const qtyMaxEffective = computed(() => {
  if (!dish.value || !dish.value.singleStockLimited) return QTY_MAX
  const r = dish.value.singleStockRemaining
  if (r == null || !Number.isFinite(Number(r))) return QTY_MAX
  return Math.max(0, Math.min(QTY_MAX, Math.floor(Number(r))))
})

const unitPrice = computed(() => {
  if (!dish.value) return null
  return formatMenuPrice(dish.value.price)
})

const totalPriceText = computed(() => {
  const u = unitPrice.value
  if (u == null) return '—'
  const t = Number(u) * Math.max(1, Math.min(qtyMaxEffective.value, quantity.value))
  return Number.isFinite(t) ? t.toFixed(2) : '—'
})

const canPay = computed(() => {
  if (!dish.value || !serviceDateYmd.value) return false
  if (!isSingleOrderServiceDate(serviceDateYmd.value)) return false
  if (unitPrice.value == null) return false
  if (dish.value.singleStockLimited) {
    const n = dish.value.singleStockRemaining
    if (n == null || n <= 0) return false
  }
  const q = Math.max(1, Math.min(qtyMaxEffective.value, quantity.value))
  if (q < 1) return false
  if (fulfillMode.value === 'delivery') {
    if (!addressRows.value.length) return false
    const row = addressRows.value[selectedIndex.value]
    return !!(row && row.id)
  }
  return true
})

function onFulfillModeChange(e) {
  const v = e?.detail?.value
  fulfillMode.value = v === 'pickup' ? 'pickup' : 'delivery'
}

function decQty() {
  if (quantity.value > 1) quantity.value -= 1
}

function incQty() {
  const cap = qtyMaxEffective.value
  if (quantity.value < cap) quantity.value += 1
}

onLoad((options) => {
  try {
    const win = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
    const { navBarTotal } = getNavbarLayout()
    const h = Math.max(240, (win.windowHeight || 667) - navBarTotal)
    scrollStyle.value = { height: `${h}px` }
  } catch {
    /* ignore */
  }
  const raw =
    (options && options.dish_id) ||
    (options && options.dishId) ||
    (options && options.id) ||
    ''
  dishIdStr.value = raw ? decodeURIComponent(String(raw)) : ''
  const svcRaw =
    (options && options.service_date) ||
    (options && options.serviceDate) ||
    (options && options.date) ||
    ''
  serviceDateYmd.value = svcRaw ? decodeURIComponent(String(svcRaw)).trim() : ''

  if (!getMemberToken()) {
    loading.value = false
    loadError.value = '请先登录'
    uni.showModal({
      title: '需要登录',
      content: '请先在「我的」中完成手机号登录后再下单。',
      confirmText: '去登录',
      success: (r) => {
        if (r.confirm) uni.switchTab({ url: '/pages/mine/index' })
        else uni.navigateBack()
      },
    })
    return
  }

  if (!dishIdStr.value) {
    loading.value = false
    loadError.value = '缺少餐品参数'
    return
  }
  if (!serviceDateYmd.value) {
    loading.value = false
    loadError.value = '缺少供餐日期'
    return
  }
  if (!isSingleOrderServiceDate(serviceDateYmd.value)) {
    loading.value = false
    loadError.value = singleOrderServiceDateError(serviceDateYmd.value)
    return
  }
  loadPage()
})

onShow(() => {
  if (!dishIdStr.value || !getMemberToken()) return
  refreshAddressesOnly()
})

async function refreshAddressesOnly() {
  try {
    const raw = await request('/api/user/me/addresses', { method: 'GET', retry: 1 })
    const list = sortAddressesDefaultFirst(normalizeAddressList(raw))
    rawAddresses.value = list
    addressRows.value = list.map((it, i) => addressListRow(it, i))
    if (selectedIndex.value >= addressRows.value.length) {
      selectedIndex.value = 0
    }
  } catch {
    /* 保留列表；首次 loadPage 会报错 */
  }
}

async function loadPage() {
  loading.value = true
  loadError.value = ''
  dish.value = null
  try {
    const [d, raw] = await Promise.all([
      fetchMenuDetail(dishIdStr.value, serviceDateYmd.value),
      request('/api/user/me/addresses', { method: 'GET', retry: 1 }),
    ])
    if (!d) throw new Error('暂无餐品数据')
    dish.value = d
    const cap = d.singleStockLimited
      ? Math.max(0, Math.min(QTY_MAX, d.singleStockRemaining != null ? Math.floor(Number(d.singleStockRemaining)) : 0))
      : QTY_MAX
    if (cap < 1) {
      loadError.value = '该日单次卡名额已售罄'
    } else if (quantity.value > cap) {
      quantity.value = cap
    }
    const list = sortAddressesDefaultFirst(normalizeAddressList(raw))
    rawAddresses.value = list
    addressRows.value = list.map((it, i) => addressListRow(it, i))
    selectedIndex.value = 0
    if (formatMenuPrice(dish.value.price) == null) {
      loadError.value = '该餐品单点价格待公布'
    }
  } catch (e) {
    const msg =
      e instanceof Error
        ? e.message
        : typeof e === 'string'
          ? e
          : '加载失败'
    loadError.value = msg || '加载失败'
  } finally {
    loading.value = false
  }
}

function goAddressList() {
  uni.navigateTo({ url: '/packageUser/pages/address/list' })
}

async function handlePay() {
  if (!canPay.value || paying.value || !dish.value) return
  const isPickup = fulfillMode.value === 'pickup'
  let addressId = null
  if (!isPickup) {
    const item = rawAddresses.value[selectedIndex.value]
    addressId = getAddressRecordId(item)
    if (!addressId) {
      uni.showToast({ title: '请选择有效配送地址', icon: 'none' })
      return
    }
  }
  const p = formatMenuPrice(dish.value.price)
  if (p == null) {
    uni.showToast({ title: '单点价格待公布', icon: 'none' })
    return
  }
  const q = Math.max(1, Math.min(qtyMaxEffective.value, quantity.value))

  paying.value = true
  uni.showLoading({ title: '创建订单…', mask: true })
  try {
    await syncWxMiniOpenidFromLogin()
    const payload = {
      dish_id: Number(dish.value.dishId),
      delivery_date: serviceDateYmd.value,
      store_pickup: isPickup,
      quantity: q,
    }
    if (!isPickup) {
      payload.member_address_id = Number(addressId)
    }
    const out = await createSingleMealOrder(payload)
    const orderId = out && typeof out === 'object' ? out.id : null
    if (orderId == null) {
      throw new Error('订单创建响应异常')
    }
    uni.showLoading({ title: '拉起支付…', mask: true })
    const pay = await fetchWechatJsapiPayParams(orderId)
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
    const area = typeof out.routing_area === 'string' ? out.routing_area : '—'
    const amt =
      out && typeof out.amount_yuan === 'string'
        ? out.amount_yuan
        : (Number(p) * q).toFixed(2)
    const pickupHint = isPickup
      ? `\n门店自提，请于供餐日到店取餐。`
      : `\n微信支付确认后将派单，骑手可在配送端查看。`
    uni.showModal({
      title: '支付成功',
      content: `¥${amt} · ${out.delivery_date || serviceDateYmd.value}\n${isPickup ? '自提' : '片区'}：${area}${pickupHint}`,
      showCancel: false,
      success: () => {
        uni.navigateBack()
      },
    })
  } catch (e) {
    const raw = e && typeof e === 'object' ? e : {}
    const errMsg = typeof raw.errMsg === 'string' ? raw.errMsg : ''
    if (errMsg.includes('cancel') || errMsg.includes('取消')) {
      uni.showToast({ title: '已取消支付', icon: 'none' })
    } else {
      const msg = e instanceof Error ? e.message : errMsg || '下单或支付失败'
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
  background: #fff;
  box-sizing: border-box;
}

.scroll {
  flex: 1;
  width: 100%;
  box-sizing: border-box;
}

.state {
  flex: 1;
  padding: 48rpx 40rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.state--err {
  color: $ok-urgent-red;
}

.body {
  padding: 24rpx 40rpx 80rpx;
}

.card {
  background: #fcfaf2;
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 28rpx;
}

.card-label {
  display: block;
  font-size: 22rpx;
  font-weight: 900;
  color: $ok-slate-400;
  margin-bottom: 16rpx;
}

.dish-name-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24rpx;
}

.dish-name {
  flex: 1;
  min-width: 0;
  font-size: 36rpx;
  font-weight: 950;
  color: $ok-slate-800;
  line-height: 1.35;
}

.dish-price-col {
  flex-shrink: 0;
  max-width: 46%;
  text-align: right;
}

.stock-row {
  margin-top: 20rpx;
  font-size: 26rpx;
  color: $ok-slate-600;
  font-weight: 800;
}
.stock-row-num {
  color: $ok-forest-green;
  font-size: 32rpx;
  font-weight: 950;
  margin: 0 4rpx;
}

.dish-meta {
  margin-top: 16rpx;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16rpx;
}

.meta-tag {
  font-size: 22rpx;
  color: $ok-forest-green;
  font-weight: 800;
  background: rgba(14, 90, 68, 0.12);
  padding: 8rpx 20rpx;
  border-radius: 16rpx;
}

.dish-price {
  font-size: 34rpx;
  font-weight: 1000;
  color: $ok-forest-green;
  line-height: 1.35;
}

.dish-price--muted {
  font-size: 26rpx;
  color: $ok-slate-400;
  font-weight: 800;
}

.dish-total-row {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 2rpx dashed rgba(14, 90, 68, 0.2);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  flex-wrap: wrap;
}

.dish-total-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12rpx 16rpx;
  min-width: 0;
  flex: 1;
}

.dish-total-label {
  font-size: 26rpx;
  font-weight: 800;
  color: $ok-slate-600;
  flex-shrink: 0;
}

.dish-total-unit-hint {
  font-size: 26rpx;
  font-weight: 800;
  color: $ok-slate-500;
  flex-shrink: 0;
}

.dish-total-amt {
  font-size: 36rpx;
  font-weight: 1000;
  color: $ok-forest-green;
  flex-shrink: 0;
}

.qty-inline {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.mode-group {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.mode-group--row {
  flex-direction: row;
  align-items: stretch;
  gap: 20rpx;
}

.mode-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  padding: 20rpx 12rpx;
  background: #fff;
  border-radius: 20rpx;
  border: 2rpx solid $ok-slate-100;
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
}

.mode-label {
  font-size: 28rpx;
  font-weight: 800;
  color: $ok-slate-800;
}

.qty-btn {
  width: 72rpx;
  height: 72rpx;
  line-height: 72rpx;
  padding: 0;
  margin: 0;
  background: #fff;
  border: 3rpx solid $ok-forest-green;
  border-radius: 16rpx;
  font-size: 40rpx;
  font-weight: 900;
  color: $ok-forest-green;
}

.qty-btn--sm {
  width: 56rpx;
  height: 56rpx;
  line-height: 56rpx;
  font-size: 32rpx;
  border-radius: 14rpx;
  border-width: 2rpx;
}

.qty-btn::after {
  border: none;
}

.qty-num {
  min-width: 48rpx;
  text-align: center;
  font-size: 36rpx;
  font-weight: 950;
  color: $ok-slate-800;
}

.qty-num--sm {
  min-width: 40rpx;
  font-size: 30rpx;
}
.addr-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8rpx;
}

.addr-manage {
  font-size: 24rpx;
  font-weight: 800;
  color: $ok-forest-green;
}

.addr-empty {
  padding: 24rpx 0;
  text-align: center;
  font-size: 26rpx;
  color: $ok-slate-500;
}

.btn-ghost {
  margin-top: 20rpx;
  background: transparent;
  color: $ok-forest-green;
  font-size: 28rpx;
  font-weight: 800;
  border: 2rpx solid $ok-forest-green;
  border-radius: 24rpx;
}

.addr-list {
  margin-top: 12rpx;
}

.addr-row {
  display: flex;
  gap: 20rpx;
  padding: 24rpx 16rpx;
  border-radius: 24rpx;
  border: 2rpx solid transparent;
  margin-bottom: 12rpx;
  background: #fff;
}

.addr-row--on {
  border-color: $ok-forest-green;
  background: rgba(14, 90, 68, 0.06);
}

.addr-radio {
  width: 44rpx;
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 4rpx;
}

.addr-dot-fill {
  width: 28rpx;
  height: 28rpx;
  border-radius: 50%;
  background: $ok-forest-green;
  margin-top: 4rpx;
  flex-shrink: 0;
}

.addr-ring {
  width: 28rpx;
  height: 28rpx;
  border: 2rpx solid $ok-slate-200;
  border-radius: 50%;
  margin-top: 4rpx;
}

.addr-body {
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

.addr-name {
  font-size: 30rpx;
  font-weight: 900;
  color: $ok-slate-800;
}

.addr-phone {
  font-size: 26rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.addr-badge {
  font-size: 20rpx;
  color: $ok-forest-green;
  font-weight: 800;
  border: 1rpx solid rgba(14, 90, 68, 0.35);
  padding: 4rpx 12rpx;
  border-radius: 12rpx;
}

.addr-line2 {
  font-size: 26rpx;
  color: $ok-slate-500;
  line-height: 1.5;
  font-weight: 600;
}

.hint-box {
  padding: 8rpx 0 32rpx;
}

.hint-title {
  display: block;
  font-size: 24rpx;
  font-weight: 900;
  color: $ok-slate-600;
  margin-bottom: 12rpx;
}

.hint-text {
  font-size: 24rpx;
  color: $ok-slate-400;
  line-height: 1.65;
  font-weight: 600;
}

.btn-pay {
  width: 100%;
  padding: 44rpx;
  background: $ok-forest-green;
  color: #fff;
  border: none;
  border-radius: 48rpx;
  font-size: 34rpx;
  font-weight: 950;
  box-shadow: 0 30rpx 60rpx rgba(14, 90, 68, 0.2);
}

.btn-pay--disabled {
  opacity: 0.45;
  box-shadow: none;
}
</style>
