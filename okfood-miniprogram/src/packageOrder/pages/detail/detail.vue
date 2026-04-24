<template>
  <view class="page">
    <OkNavbar show-back title="" />
    <view v-if="loading" class="detail-state">加载中…</view>
    <view v-else-if="loadError" class="detail-state detail-state--err">{{ loadError }}</view>
    <scroll-view
      v-else-if="dish"
      :key="dish.dishId || 'dish'"
      scroll-y
      class="scroll"
      :show-scrollbar="false"
      :style="scrollStyle"
    >
      <view class="detail-page">
        <view class="detail-hero">
          <image class="hero-img" :src="dish.img" mode="aspectFill" @error="onImgErr" />
        </view>
        <view class="detail-body">
          <view class="title-row">
            <text class="detail-title">{{ dish.name }}</text>
            <text class="limit-tag">{{ dish.day }}限定</text>
          </view>
          <view class="detail-price-card">
            <view class="price-card-left">
              <text class="p-sub">自律首选价 / Single Order</text>
              <text v-if="formatMenuPrice(dish.price) != null" class="p-val">¥ {{ formatMenuPrice(dish.price) }}</text>
              <text v-else class="p-val p-val--pending">待公布</text>
            </view>
            <view class="price-card-right">
              <text class="p-hint">包月订阅更优惠 👌</text>
              <view v-if="showDayStockBlock" class="day-stock-line">
                <block v-if="dish.singleStockLimited">
                  <text class="day-stock-txt">当日剩余</text>
                  <text class="day-stock-num">{{ dish.singleStockRemaining ?? 0 }}</text>
                  <text class="day-stock-unit">份</text>
                </block>
                <text v-else class="day-stock-unlimited">当日单点不限量</text>
              </view>
            </view>
          </view>
          <view class="ingredient-box">
            <text class="ingredient-title">🔍 核心配料明细</text>
            <text class="ingredient-list">{{ dish.ingredients || '—' }}</text>
          </view>
          <button
            v-if="canSubmitSingleOrder"
            class="btn-order-confirm"
            @click="handleBuy"
          >确认订单信息</button>
        </view>
      </view>
    </scroll-view>
    <view v-else class="detail-state detail-state--err">加载异常，请返回重试</view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  fetchMenuDetail,
  formatMenuPrice,
  isSingleOrderServiceDate,
  singleOrderServiceDateError,
} from '@/utils/menuApi.js'
import { getNavbarLayout } from '@/utils/navbar.js'
import { getMemberToken } from '@/utils/api.js'

const dish = ref(null)
const loading = ref(true)
const loadError = ref('')
/** 供餐日 YYYY-MM-DD，来自周菜单跳转 */
const serviceDateYmd = ref('')
const canSubmitSingleOrder = computed(() => {
  if (!isSingleOrderServiceDate(serviceDateYmd.value)) return false
  const d = dish.value
  if (!d) return true
  if (d.singleStockLimited) {
    const n = d.singleStockRemaining
    if (n == null || n <= 0) return false
  }
  return true
})

/** 有供餐日才展示「当日剩余」与订阅提示同列，否则仅保留原右侧一句提示在下方 v-else 分支 */
const showDayStockBlock = computed(() => !!(serviceDateYmd.value && dish.value))
/** scroll-view 必须用确定 px高度，微信里 flex+calc 易导致子节点不渲染 */
const scrollStyle = ref({ height: '400px' })

onLoad((options) => {
  try {
    const win = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
    const { navBarTotal } = getNavbarLayout()
    const h = Math.max(240, (win.windowHeight || 667) - navBarTotal)
    scrollStyle.value = { height: `${h}px` }
  } catch {
    /* 使用默认 height */
  }
  const raw =
    (options && options.dish_id) ||
    (options && options.dishId) ||
    (options && options.food_id) ||
    (options && options.foodId) ||
    (options && options.id) ||
    (options && options.order_id) ||
    (options && options.orderId) ||
    ''
  const dishId = raw ? decodeURIComponent(String(raw)) : ''
  const svcRaw =
    (options && options.service_date) ||
    (options && options.serviceDate) ||
    (options && options.date) ||
    ''
  serviceDateYmd.value = svcRaw ? decodeURIComponent(String(svcRaw)).trim() : ''
  if (!dishId) {
    loading.value = false
    loadError.value = '缺少餐品参数'
    return
  }
  loadDetail(dishId)
})

async function loadDetail(dishId) {
  loading.value = true
  loadError.value = ''
  dish.value = null
  try {
    const d = await fetchMenuDetail(dishId, serviceDateYmd.value)
    if (!d) throw new Error('暂无数据')
    dish.value = d
  } catch (e) {
    const msg =
      e instanceof Error
        ? e.message
        : typeof e === 'string'
          ? e
          : e && typeof e === 'object' && 'errMsg' in e && typeof e.errMsg === 'string'
            ? e.errMsg
            : '加载失败'
    loadError.value = msg || '加载失败'
  } finally {
    loading.value = false
  }
}

const fallback =
  'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=600'

function onImgErr() {
  if (dish.value) dish.value = { ...dish.value, img: fallback }
}

function handleBuy() {
  if (!dish.value) return
  if (!canSubmitSingleOrder.value) {
    const msg = singleOrderServiceDateError(serviceDateYmd.value)
    uni.showToast({ title: msg, icon: 'none' })
    return
  }
  const p = formatMenuPrice(dish.value.price)
  if (p == null) {
    uni.showToast({ title: '单点价格待公布', icon: 'none' })
    return
  }
  if (!getMemberToken()) {
    uni.showModal({
      title: '需要登录',
      content: '请先在「我的」中完成手机号登录后再下单。',
      confirmText: '去登录',
      success: (r) => {
        if (r.confirm) uni.switchTab({ url: '/pages/mine/index' })
      },
    })
    return
  }
  if (!serviceDateYmd.value) {
    uni.showToast({ title: '缺少供餐日期，请从周菜单进入', icon: 'none' })
    return
  }
  const id = encodeURIComponent(String(dish.value.dishId))
  const d = encodeURIComponent(serviceDateYmd.value)
  uni.navigateTo({
    url: `/packageOrder/pages/singleConfirm/singleConfirm?dish_id=${id}&service_date=${d}`,
  })
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
  width: 100%;
  box-sizing: border-box;
  background: #fff;
}

.detail-state {
  flex: 1;
  min-height: 200rpx;
  padding: 48rpx 40rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.detail-state--err {
  color: $ok-urgent-red;
}

.detail-page {
  min-height: 100%;
}

.detail-hero {
  width: 100%;
  height: 70vw;
  max-height: 100vw;
  position: relative;
}

.hero-img {
  width: 100%;
  height: 100%;
}

.detail-body {
  padding: 60rpx 40rpx 80rpx;
}

.title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20rpx;
  margin-bottom: 20rpx;
}

.detail-title {
  flex: 1;
  font-size: 48rpx;
  font-weight: 950;
  color: $ok-slate-800;
}

.limit-tag {
  background: $ok-forest-green;
  color: #fff;
  font-size: 20rpx;
  padding: 8rpx 20rpx;
  border-radius: 16rpx;
  font-weight: 900;
  flex-shrink: 0;
}

.detail-price-card {
  background: #fcfaf2;
  padding: 40rpx;
  border-radius: 48rpx;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24rpx;
  margin-bottom: 60rpx;
}

.price-card-left {
  flex: 1;
  min-width: 0;
}

.price-card-right {
  flex-shrink: 0;
  max-width: 44%;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 16rpx;
  text-align: right;
  padding-top: 4rpx;
}

.day-stock-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: flex-end;
  gap: 6rpx 8rpx;
}

.day-stock-txt {
  font-size: 24rpx;
  color: $ok-slate-500;
  font-weight: 800;
}

.day-stock-num {
  font-size: 40rpx;
  font-weight: 950;
  color: $ok-forest-green;
  line-height: 1;
}

.day-stock-unit {
  font-size: 24rpx;
  color: $ok-slate-500;
  font-weight: 800;
}

.day-stock-unlimited {
  font-size: 24rpx;
  color: $ok-slate-400;
  font-weight: 700;
}

.p-sub {
  display: block;
  font-size: 20rpx;
  color: $ok-slate-400;
  font-weight: 900;
  margin-bottom: 8rpx;
}

.p-val {
  font-size: 64rpx;
  font-weight: 1000;
  color: $ok-forest-green;
  font-style: italic;
}

.p-val--pending {
  font-size: 40rpx;
  font-style: normal;
  color: $ok-slate-400;
}

.p-hint {
  font-size: 22rpx;
  opacity: 0.5;
  font-weight: 700;
  max-width: 220rpx;
  text-align: right;
  line-height: 1.4;
}

.ingredient-box {
  border-top: 1px solid $ok-slate-100;
  padding-top: 40rpx;
}

.ingredient-title {
  display: block;
  font-size: 24rpx;
  font-weight: 900;
  color: $ok-forest-green;
  letter-spacing: 2rpx;
  margin-bottom: 24rpx;
}

.ingredient-list {
  font-size: 28rpx;
  color: $ok-slate-400;
  line-height: 1.8;
  font-weight: 700;
  font-style: italic;
}

.btn-order-confirm {
  width: 100%;
  padding: 44rpx;
  background: $ok-forest-green;
  color: #fff;
  border: none;
  border-radius: 48rpx;
  font-size: 34rpx;
  font-weight: 950;
  margin-top: 80rpx;
  box-shadow: 0 30rpx 60rpx rgba(14, 90, 68, 0.2);
}
</style>
