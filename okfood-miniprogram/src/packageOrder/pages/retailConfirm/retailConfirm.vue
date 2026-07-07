<template>
  <view class="page">
    <OkNavbar show-back title="订单结算" />
    <view v-if="loading" class="state">加载中…</view>
    <view v-else-if="loadError" class="state state--err">{{ loadError }}</view>
    <scroll-view v-else scroll-y class="scroll" :show-scrollbar="false" :style="scrollStyle">
      <view class="body">
        <!-- 配送地址（普通零售商品仅支持配送到家） -->
        <view class="card delivery-card">
          <view class="delivery-head">
            <text class="delivery-tag">外送</text>
            <text class="delivery-store">{{ storeName || '门店商城' }}</text>
          </view>
          <view class="delivery-divider" />
          <view class="addr-head">
            <view class="addr-head-left">
              <text class="addr-pin">📍</text>
              <text class="card-label card-label--inline">配送地址</text>
            </view>
            <text class="addr-manage" @tap="goAddressList">
              {{ addressRows.length ? '选择地址 ›' : '去添加 ›' }}
            </text>
          </view>
          <view v-if="!addressRows.length" class="addr-empty">
            <text class="addr-empty-txt">暂无地址，请先添加配送地址</text>
            <button type="button" class="btn-ghost" hover-class="none" @tap="goAddressList">添加地址</button>
          </view>
          <view v-else class="addr-list">
            <view
              v-for="(row, i) in addressRows"
              :key="row.id || i"
              class="addr-row"
              :class="{ 'addr-row--on': selectedIndex === i }"
              :data-index="i"
              @tap="onAddressRowTap"
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

        <!-- 商品信息 -->
        <view v-if="product" class="card product-card">
          <text class="card-label">商品明细</text>
          <view class="product-row">
            <image
              v-if="productImage"
              class="product-img"
              :src="productImage"
              mode="aspectFill"
            />
            <view v-else class="product-img product-img--placeholder">
              <text class="product-img-ph">商</text>
            </view>
            <view class="product-info">
              <text class="product-name">{{ product.title }}</text>
              <text v-if="product.subtitle" class="product-sub">{{ product.subtitle }}</text>
              <view class="product-price-row">
                <view class="product-price-group">
                  <text v-if="showListPrice" class="product-price-tag">限时特惠</text>
                  <view class="product-price-line">
                    <text class="product-price">¥ {{ unitPriceText }}</text>
                    <text v-if="showListPrice" class="product-list-price">¥ {{ unitListPriceText }}</text>
                  </view>
                </view>
                <view class="qty-inline" @catchtap="onStopTapBubble">
                  <button type="button" class="qty-btn qty-btn--sm" @tap="decQty">−</button>
                  <text class="qty-num qty-num--sm">{{ quantity }}</text>
                  <button type="button" class="qty-btn qty-btn--sm" @tap="incQty">+</button>
                </view>
              </view>
            </view>
          </view>
          <view v-if="showListPrice" class="product-discount-row">
            <text class="product-discount-label">商品原价</text>
            <text class="product-discount-orig">¥ {{ origSubtotalText }}</text>
          </view>
          <view v-if="productSaveText" class="product-discount-row">
            <text class="product-discount-label">商品优惠</text>
            <text class="product-discount-save">-¥ {{ productSaveText }}</text>
          </view>
          <view v-if="couponSaveText" class="product-discount-row">
            <text class="product-discount-label">优惠券</text>
            <text class="product-discount-save">-¥ {{ couponSaveText }}</text>
          </view>
          <view class="product-total-row">
            <text class="product-total-label">应付</text>
            <view class="product-total-right">
              <text v-if="totalBeforePayText && totalBeforePayText !== payableText" class="product-total-orig">
                ¥ {{ totalBeforePayText }}
              </text>
              <text class="product-total-amt">¥ {{ payableText }}</text>
            </view>
          </view>
        </view>

        <!-- 优惠券 -->
        <view v-if="availableCoupons.length" class="card coupon-card">
          <picker
            mode="selector"
            :range="availableCoupons"
            range-key="template_name"
            @change="onCouponPick"
          >
            <view class="coupon-row">
              <view class="coupon-left">
                <text class="coupon-icon">🎫</text>
                <text class="coupon-label">优惠券</text>
              </view>
              <view class="coupon-right">
                <text v-if="selectedCoupon" class="coupon-val coupon-val--on">
                  -¥{{ selectedCoupon.discount_yuan }}
                </text>
                <text v-else class="coupon-val">可使用 {{ availableCoupons.length }} 张</text>
                <text class="coupon-arr">›</text>
              </view>
            </view>
          </picker>
        </view>

        <view class="hint-box">
          <text class="hint-title">支付说明</text>
          <text class="hint-text">
            点击「立即下单」将调起微信支付。支付成功后门店将安排配送。
          </text>
        </view>
      </view>
    </scroll-view>

    <view v-if="!loading && !loadError && product" class="pay-footer">
      <view class="pay-footer-left">
        <view class="pay-footer-price-col">
          <view class="pay-footer-top">
            <text class="pay-footer-label">合计</text>
            <text class="pay-footer-amt">¥ {{ payableText }}</text>
          </view>
          <text v-if="totalSaveText" class="pay-footer-save">已优惠 ¥{{ totalSaveText }}</text>
        </view>
      </view>
      <button
        class="btn-pay"
        hover-class="none"
        :class="{ 'btn-pay--disabled': paying }"
        @tap="onPayButtonTap"
      >
        {{ paying ? '处理中…' : '立即下单' }}
      </button>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { onLoad, onShow, onReady } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  getPageScrollStyle,
  schedulePageScrollLayout,
  FIXED_FOOTER_RESERVE_PX,
} from '@/utils/navbar.js'
import { getMemberToken, request } from '@/utils/api.js'
import { fetchRetailMenu, fetchStoreInfo } from '@/utils/catalogApi.js'
import { formatMenuPrice } from '@/utils/menuApi.js'
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

const scrollStyle = ref(getPageScrollStyle(0, FIXED_FOOTER_RESERVE_PX))
const productId = ref(0)
const product = ref(null)
const storeName = ref('')
const loading = ref(true)
const loadError = ref('')
const quantity = ref(1)
const paying = ref(false)
const addressRows = ref([])
const rawAddresses = ref([])
const selectedIndex = ref(0)
const availableCoupons = ref([])
const selectedCouponId = ref(null)
const selectedCoupon = computed(() => {
  const id = selectedCouponId.value
  if (id == null) return null
  return availableCoupons.value.find((c) => Number(c.id) === Number(id)) || null
})

const productImage = computed(() => {
  const url = product.value?.cover_image_url
  return typeof url === 'string' && url.trim() ? url.trim() : ''
})

const unitPriceText = computed(() => {
  const list = formatMenuPrice(product.value?.unit_price_yuan)
  if (list == null) return '—'
  return list.toFixed(2)
})

/** 划线原价（单价） */
const listPriceNum = computed(() => formatMenuPrice(product.value?.list_price_yuan))

/** 划线价高于售价时展示优惠感 */
const showListPrice = computed(() => {
  const sale = Number(unitPriceText.value)
  const list = listPriceNum.value
  if (!Number.isFinite(sale) || list == null) return false
  return list > sale
})

const unitListPriceText = computed(() => {
  if (!showListPrice.value || listPriceNum.value == null) return null
  return listPriceNum.value.toFixed(2)
})

const subtotal = computed(() => {
  const u = Number(unitPriceText.value)
  if (!Number.isFinite(u)) return null
  return (u * Math.max(1, quantity.value)).toFixed(2)
})

/** 商品原价小计（划线价 × 数量） */
const origSubtotalText = computed(() => {
  if (!showListPrice.value || listPriceNum.value == null) return null
  return (listPriceNum.value * Math.max(1, quantity.value)).toFixed(2)
})

/** 商品本身优惠金额（不含券） */
const productSaveText = computed(() => {
  if (!showListPrice.value || origSubtotalText.value == null || subtotal.value == null) return null
  const save = Number(origSubtotalText.value) - Number(subtotal.value)
  return save > 0 ? save.toFixed(2) : null
})

/** 优惠券抵扣金额 */
const couponSaveText = computed(() => {
  if (!selectedCoupon.value) return null
  const n = Number(selectedCoupon.value.discount_yuan)
  return Number.isFinite(n) && n > 0 ? n.toFixed(2) : null
})

/** 优惠前应付（商品售价小计，用于与券后价对比） */
const totalBeforePayText = computed(() => subtotal.value)

/** 合计应付（含券后） */
const payableText = computed(() => {
  const base = subtotal.value
  if (base == null) return '—'
  const disc = couponSaveText.value != null ? Number(couponSaveText.value) : 0
  return Math.max(0.01, Number(base) - disc).toFixed(2)
})

/** 底部「已优惠」合计（商品优惠 + 券） */
const totalSaveText = computed(() => {
  let total = 0
  if (productSaveText.value) total += Number(productSaveText.value)
  if (couponSaveText.value) total += Number(couponSaveText.value)
  return total > 0 ? total.toFixed(2) : null
})

/** 不可支付时的原因（空串表示可支付） */
const payBlockReason = computed(() => {
  if (paying.value) return ''
  if (!product.value) return '商品加载中，请稍候'
  if (!addressRows.value.length) return '请先添加配送地址'
  const item = rawAddresses.value[selectedIndex.value]
  if (!getAddressRecordId(item)) return '请选择有效配送地址'
  return ''
})

function applyScrollLayout() {
  schedulePageScrollLayout((style) => {
    scrollStyle.value = style
  }, FIXED_FOOTER_RESERVE_PX)
}

function applyStoreInfo(store) {
  storeName.value = store?.store_name?.trim() || ''
}

function decQty() {
  if (quantity.value > 1) quantity.value -= 1
  void loadCoupons()
}

function incQty() {
  if (quantity.value < 50) quantity.value += 1
  void loadCoupons()
}

function onStopTapBubble() {
  /* 阻止数量区点击冒泡 */
}

function onAddressRowTap(e) {
  const idx = Number(e?.currentTarget?.dataset?.index)
  if (Number.isFinite(idx) && idx >= 0) {
    selectedIndex.value = idx
  }
}

function onCouponPick(e) {
  const idx = Number(e?.detail?.value)
  const c = availableCoupons.value[idx]
  selectedCouponId.value = c ? c.id : null
}

function applyAddressList(raw) {
  const list = sortAddressesDefaultFirst(normalizeAddressList(raw))
  rawAddresses.value = list
  addressRows.value = list.map((item, i) => addressListRow(item, i))
  if (selectedIndex.value >= addressRows.value.length) {
    selectedIndex.value = 0
  }
}

async function loadCoupons() {
  if (!productId.value) return
  try {
    const list = await listAvailableMemberCoupons({
      biz_type: 'store_retail',
      retail_product_id: productId.value,
      quantity: quantity.value,
      store_pickup: false,
    })
    availableCoupons.value = Array.isArray(list) ? list : []
    if (
      selectedCouponId.value != null &&
      !availableCoupons.value.some((c) => Number(c.id) === Number(selectedCouponId.value))
    ) {
      selectedCouponId.value = null
    }
  } catch {
    availableCoupons.value = []
  }
}

async function loadPage() {
  loading.value = true
  loadError.value = ''
  try {
    const [menu, store] = await Promise.all([
      fetchRetailMenu(),
      fetchStoreInfo().catch(() => null),
    ])
    applyStoreInfo(store)
    let found = null
    for (const cat of menu) {
      for (const p of cat.products || []) {
        if (Number(p.id) === Number(productId.value)) {
          found = { ...p, category_id: cat.id }
          break
        }
      }
      if (found) break
    }
    if (!found) throw new Error('商品不存在或已下架')
    product.value = found
    const raw = await request('/api/user/me/addresses', { method: 'GET', retry: 1 })
    applyAddressList(raw)
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

function onPayButtonTap() {
  const reason = payBlockReason.value
  if (reason) {
    uni.showToast({ title: reason, icon: 'none', duration: 2800 })
    return
  }
  if (paying.value || !product.value) return
  void handlePay()
}

async function handlePay() {
  if (paying.value || !product.value) return
  const item = rawAddresses.value[selectedIndex.value]
  const addressId = getAddressRecordId(item)
  if (!addressId) {
    uni.showToast({ title: '请选择有效配送地址', icon: 'none' })
    return
  }
  paying.value = true
  uni.showLoading({ title: '创建订单…', mask: true })
  try {
    await syncWxMiniOpenidFromLogin()
    const payload = {
      retail_product_id: Number(productId.value),
      store_pickup: false,
      quantity: Math.max(1, quantity.value),
      member_address_id: Number(addressId),
    }
    if (selectedCouponId.value != null) {
      payload.member_coupon_id = Math.floor(Number(selectedCouponId.value))
    }
    const out = await createRetailOrder(payload)
    const orderId = out?.id
    if (orderId == null) throw new Error('订单创建响应异常')
    uni.showLoading({ title: '拉起支付…', mask: true })
    const payResult = await payRetailOrderWechat(orderId)
    if (!payResult.paySynced) {
      uni.showToast({ title: '支付成功，订单同步中请稍后刷新', icon: 'none', duration: 3000 })
    }
    showOkAlert({
      title: '支付成功',
      content: '您的商城订单已提交',
      tone: 'success',
      showCancel: false,
      success: () => {
        try {
          uni.setStorageSync('okfood_open_orders_tab', 'retail')
        } catch {
          /* ignore */
        }
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

onReady(() => {
  applyScrollLayout()
})

onLoad((options) => {
  applyScrollLayout()
  const raw = options?.retail_product_id || options?.product_id || ''
  const id = Math.floor(Number(decodeURIComponent(String(raw || ''))))
  if (!Number.isFinite(id) || id < 1) {
    loadError.value = '缺少商品参数'
    loading.value = false
    return
  }
  productId.value = id
  if (!getMemberToken()) {
    loading.value = false
    loadError.value = '请先登录'
    showOkAlert({
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
  void loadPage()
})

onShow(() => {
  applyScrollLayout()
  if (!productId.value || !getMemberToken()) return
  void request('/api/user/me/addresses', { method: 'GET', retry: 1 })
    .then(applyAddressList)
    .catch(() => {})
  void loadCoupons()
})
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
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

.state {
  flex: 1;
  min-height: 50vh;
  padding: 48rpx 40rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
  box-sizing: border-box;
}

.state--err {
  color: $ok-urgent-red;
}

.body {
  padding: 24rpx 32rpx 32rpx;
}

.card {
  background: #fff;
  border-radius: 24rpx;
  padding: 28rpx 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 20rpx rgba(15, 23, 42, 0.04);
}

.card-label {
  display: block;
  font-size: 22rpx;
  font-weight: 900;
  color: $ok-slate-400;
  margin-bottom: 16rpx;
}

.card-label--inline {
  margin-bottom: 0;
  font-size: 28rpx;
  color: $ok-slate-700;
}

/* 配送卡片 */
.delivery-head {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 4rpx;
}

.delivery-tag {
  font-size: 20rpx;
  font-weight: 900;
  color: #fff;
  background: $ok-forest-green;
  padding: 4rpx 14rpx;
  border-radius: 8rpx;
  flex-shrink: 0;
}

.delivery-store {
  font-size: 30rpx;
  font-weight: 900;
  color: $ok-slate-800;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delivery-divider {
  height: 1rpx;
  background: $ok-slate-100;
  margin: 20rpx 0;
}

.mode-tabs {
  display: flex;
  gap: 16rpx;
}

.mode-tab {
  flex: 1;
  padding: 18rpx 12rpx;
  text-align: center;
  border-radius: 16rpx;
  background: $ok-slate-50;
  border: 2rpx solid transparent;
  transition: all 0.15s;
}

.mode-tab--on {
  background: rgba(115, 176, 84, 0.1);
  border-color: $ok-forest-green;
}

.mode-tab__txt {
  font-size: 28rpx;
  font-weight: 800;
  color: $ok-slate-600;
}

.mode-tab--on .mode-tab__txt {
  color: $ok-forest-green;
}

.pickup-hint {
  margin-top: 20rpx;
  padding: 20rpx 24rpx;
  background: rgba(115, 176, 84, 0.06);
  border-radius: 16rpx;
}

.pickup-store-head {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 12rpx;
}

.pickup-store-card {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 20rpx 24rpx;
  border-radius: 20rpx;
  background: $ok-slate-50;
  border: 2rpx solid transparent;
}

.pickup-store-card--tap:active {
  background: rgba(115, 176, 84, 0.08);
  border-color: rgba(115, 176, 84, 0.25);
}

.pickup-store-main {
  flex: 1;
  min-width: 0;
}

.pickup-store-name {
  display: block;
  font-size: 30rpx;
  font-weight: 900;
  color: $ok-slate-800;
  line-height: 1.4;
}

.pickup-store-addr {
  display: block;
  margin-top: 8rpx;
  font-size: 26rpx;
  color: $ok-slate-500;
  font-weight: 600;
  line-height: 1.5;
}

.pickup-store-addr--muted {
  color: $ok-slate-400;
}

.pickup-store-meta {
  flex-shrink: 0;
  padding-top: 4rpx;
}

.pickup-store-dist {
  font-size: 22rpx;
  font-weight: 800;
  color: $ok-forest-green;
  white-space: nowrap;
}

.pickup-store-nav {
  flex-shrink: 0;
  font-size: 24rpx;
  font-weight: 800;
  color: $ok-forest-green;
  padding-top: 4rpx;
}

.pickup-hint-txt {
  font-size: 24rpx;
  color: $ok-slate-500;
  font-weight: 600;
  line-height: 1.5;
}

/* 地址 */
.addr-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8rpx;
}

.addr-head-left {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.addr-pin {
  font-size: 28rpx;
  line-height: 1;
}

.addr-manage {
  font-size: 24rpx;
  font-weight: 800;
  color: $ok-forest-green;
}

.addr-empty {
  padding: 24rpx 0 8rpx;
  text-align: center;
}

.addr-empty-txt {
  display: block;
  font-size: 26rpx;
  color: $ok-slate-400;
  font-weight: 600;
}

.btn-ghost {
  margin-top: 20rpx;
  background: transparent;
  color: $ok-forest-green;
  font-size: 28rpx;
  font-weight: 800;
  border: 2rpx solid $ok-forest-green;
  border-radius: 40rpx;
  padding: 12rpx 48rpx;
}

.btn-ghost::after {
  border: none;
}

.addr-list {
  margin-top: 8rpx;
}

.addr-row {
  display: flex;
  gap: 20rpx;
  padding: 20rpx 16rpx;
  border-radius: 20rpx;
  border: 2rpx solid transparent;
  margin-bottom: 12rpx;
  background: $ok-slate-50;
}

.addr-row--on {
  border-color: $ok-forest-green;
  background: rgba(115, 176, 84, 0.06);
}

.addr-radio {
  width: 40rpx;
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 6rpx;
}

.addr-dot-fill {
  width: 28rpx;
  height: 28rpx;
  border-radius: 50%;
  background: $ok-forest-green;
}

.addr-ring {
  width: 28rpx;
  height: 28rpx;
  border: 2rpx solid $ok-slate-200;
  border-radius: 50%;
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
  border: 1rpx solid rgba(115, 176, 84, 0.35);
  padding: 4rpx 12rpx;
  border-radius: 12rpx;
}

.addr-line2 {
  font-size: 26rpx;
  color: $ok-slate-500;
  line-height: 1.5;
  font-weight: 600;
}

/* 商品 */
.product-row {
  display: flex;
  gap: 24rpx;
  align-items: flex-start;
}

.product-img {
  width: 160rpx;
  height: 160rpx;
  border-radius: 16rpx;
  flex-shrink: 0;
  background: $ok-slate-100;
}

.product-img--placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(115, 176, 84, 0.12);
}

.product-img-ph {
  font-size: 48rpx;
  font-weight: 900;
  color: $ok-forest-green;
  opacity: 0.5;
}

.product-info {
  flex: 1;
  min-width: 0;
}

.product-name {
  display: block;
  font-size: 30rpx;
  font-weight: 900;
  color: $ok-slate-800;
  line-height: 1.4;
}

.product-sub {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: $ok-slate-400;
  font-weight: 600;
  line-height: 1.4;
}

.product-price-row {
  margin-top: 16rpx;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16rpx;
}

.product-price-group {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  min-width: 0;
}

.product-price-tag {
  align-self: flex-start;
  font-size: 20rpx;
  font-weight: 900;
  color: $ok-urgent-red;
  background: rgba(239, 68, 68, 0.08);
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
  line-height: 1.3;
}

.product-price-line {
  display: flex;
  align-items: baseline;
  gap: 12rpx;
  flex-wrap: wrap;
}

.product-price {
  font-size: 32rpx;
  font-weight: 1000;
  color: $ok-forest-green;
}

.product-list-price {
  font-size: 24rpx;
  font-weight: 600;
  color: $ok-slate-400;
  text-decoration: line-through;
  line-height: 1.2;
}

.product-discount-row {
  margin-top: 16rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.product-discount-label {
  font-size: 24rpx;
  font-weight: 700;
  color: $ok-slate-500;
}

.product-discount-orig {
  font-size: 24rpx;
  font-weight: 600;
  color: $ok-slate-400;
  text-decoration: line-through;
}

.product-discount-save {
  font-size: 26rpx;
  font-weight: 900;
  color: $ok-urgent-red;
}

.product-total-row {
  margin-top: 24rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid $ok-slate-100;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.product-total-label {
  font-size: 26rpx;
  font-weight: 800;
  color: $ok-slate-500;
}

.product-total-right {
  display: flex;
  align-items: baseline;
  gap: 12rpx;
}

.product-total-orig {
  font-size: 24rpx;
  color: $ok-slate-400;
  text-decoration: line-through;
  font-weight: 600;
}

.product-total-amt {
  font-size: 36rpx;
  font-weight: 1000;
  color: $ok-forest-green;
}

.fee-hint {
  display: block;
  margin-top: 16rpx;
  font-size: 22rpx;
  color: $ok-slate-400;
  font-weight: 600;
  line-height: 1.45;
}

/* 数量步进器 */
.qty-inline {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.qty-btn {
  width: 56rpx;
  height: 56rpx;
  line-height: 56rpx;
  padding: 0;
  margin: 0;
  background: #fff;
  border: 2rpx solid $ok-forest-green;
  border-radius: 12rpx;
  font-size: 32rpx;
  font-weight: 900;
  color: $ok-forest-green;
}

.qty-btn--sm {
  width: 48rpx;
  height: 48rpx;
  line-height: 48rpx;
  font-size: 28rpx;
  border-radius: 10rpx;
}

.qty-btn::after {
  border: none;
}

.qty-num {
  min-width: 40rpx;
  text-align: center;
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-slate-800;
}

.qty-num--sm {
  min-width: 36rpx;
  font-size: 28rpx;
}

/* 优惠券 */
.coupon-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.coupon-left {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.coupon-icon {
  font-size: 32rpx;
  line-height: 1;
}

.coupon-label {
  font-size: 28rpx;
  font-weight: 800;
  color: $ok-slate-700;
}

.coupon-right {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.coupon-val {
  font-size: 26rpx;
  color: $ok-slate-400;
  font-weight: 700;
}

.coupon-val--on {
  color: $ok-urgent-red;
  font-weight: 900;
}

.coupon-arr {
  font-size: 32rpx;
  color: $ok-slate-300;
  font-weight: 700;
}

/* 说明 */
.hint-box {
  padding: 8rpx 8rpx 32rpx;
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

/* 底栏 */
.pay-footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  padding: 16rpx 32rpx;
  padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
  background: #fff;
  box-shadow: 0 -8rpx 24rpx rgba(15, 23, 42, 0.06);
  box-sizing: border-box;
}

.pay-footer-left {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  min-width: 0;
}

.pay-footer-price-col {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.pay-footer-top {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
}

.pay-footer-save {
  font-size: 22rpx;
  font-weight: 800;
  color: $ok-urgent-red;
  line-height: 1.3;
}

.pay-footer-label {
  font-size: 26rpx;
  font-weight: 800;
  color: $ok-slate-600;
}

.pay-footer-amt {
  font-size: 40rpx;
  font-weight: 1000;
  color: $ok-forest-green;
}

.btn-pay {
  flex: 1;
  max-width: 360rpx;
  padding: 22rpx 40rpx;
  background: $ok-forest-green;
  color: #fff;
  border: none;
  border-radius: 48rpx;
  font-size: 30rpx;
  font-weight: 900;
  line-height: 1.35;
  box-shadow: 0 12rpx 28rpx rgba(115, 176, 84, 0.25);
}

.btn-pay::after {
  border: none;
}

.btn-pay--disabled {
  opacity: 0.45;
  box-shadow: none;
}
</style>
