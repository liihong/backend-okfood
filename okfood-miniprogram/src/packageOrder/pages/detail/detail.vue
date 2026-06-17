<template>
  <view class="page">
    <!-- 沉浸式大图通顶：无整块白 Navbar，仅用悬浮返回（半透底色保证各种封面上可点） -->
    <view class="detail-float-back-hit" :style="floatBackHitStyle" @tap="goBack">
      <text class="detail-float-back-ico">‹</text>
    </view>
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
          <view v-if="dish.spiceLabel" class="detail-spice-strip">
            <text class="detail-spice-txt">辣度：{{ dish.spiceLabel }}</text>
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
                  <template v-if="!isSingleOrderStockAvailable(dish)">
                    <text class="day-stock-soldout">售罄</text>
                  </template>
                  <template v-else>
                    <text class="day-stock-txt">当日剩余</text>
                    <text class="day-stock-num">{{ dish.singleStockRemaining ?? 0 }}</text>
                    <text class="day-stock-unit">份</text>
                  </template>
                </block>
                <text v-else class="day-stock-soldout">售罄</text>
              </view>
            </view>
          </view>
          <view class="ingredient-box">
            <text class="ingredient-title">🔍 核心配料明细</text>
            <text class="ingredient-list">{{ dish.ingredients || '—' }}</text>
          </view>
          <button
            v-if="showOrderButton"
            class="btn-order-confirm"
            @click="handleBuy"
          >确认订单信息</button>
        </view>
      </view>
    </scroll-view>
    <view v-else class="detail-state detail-state--err">加载异常，请返回重试</view>
    <OkAlertHost />
  </view>
</template>

<script setup>
import OkAlertHost from '@/components/OkAlertHost/OkAlertHost.vue'
import { showOkAlert } from '@/utils/okAlert.js'
import { ref, computed, nextTick } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import {
  canSubmitSingleOrder,
  fetchMenuDetail,
  formatMenuPrice,
  isSingleOrderStockAvailable,
  singleOrderBlockReason,
} from '@/utils/menuApi.js'
import { MEAL_PERIOD_DINNER, MEAL_PERIOD_LUNCH } from '@/utils/memberMealPeriod.js'
import { getNavbarLayout } from '@/utils/navbar.js'
import { getMemberToken } from '@/utils/api.js'

const dish = ref(null)
const loading = ref(true)
const loadError = ref('')
/** 供餐日 YYYY-MM-DD，来自周菜单跳转 */
const serviceDateYmd = ref('')
/** 餐段 lunch/dinner，默认午餐 */
const mealPeriod = ref(MEAL_PERIOD_LUNCH)

const showOrderButton = computed(() =>
  canSubmitSingleOrder(dish.value, serviceDateYmd.value),
)

/** 有供餐日时在价格卡右侧展示「当日剩余 / 售罄」 */
const showDayStockBlock = computed(() => !!(serviceDateYmd.value && dish.value))

/** scroll-view 必须用确定 px高度，微信里 flex+calc 易导致子节点不渲染 */
const scrollStyle = ref({ height: '400px' })
/** 与微信胶囊纵向居中对齐的悬浮返回键位置（top / left px） */
const floatBackHitStyle = ref({
  top: '48px',
  left: '12px',
})

function syncImmersionChrome() {
  const win = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
  const lay = getNavbarLayout()
  let menuTop = lay.statusBarHeight + 6
  let menuHeight = 32
  // #ifdef MP-WEIXIN
  try {
    const rect = uni.getMenuButtonBoundingClientRect()
    if (rect && typeof rect.top === 'number' && typeof rect.height === 'number') {
      menuTop = rect.top
      menuHeight = rect.height
    }
  } catch {
    /* ignore */
  }
  // #endif
  /** 触控块约 88rpx 高，折算 px 后与胶囊竖直居中 */
  let hitPx = 44
  try {
    if (typeof uni.upx2px === 'function') {
      hitPx = Math.max(36, uni.upx2px(88))
    }
  } catch {
    hitPx = 44
  }
  const top = Math.max(lay.statusBarHeight, Math.round(menuTop + (menuHeight - hitPx) / 2))
  floatBackHitStyle.value = {
    top: `${top}px`,
    left: `${Math.round((win.safeAreaInsets && win.safeAreaInsets.left) || 0) + 12}px`,
  }
  /** 沉浸式无自定义顶栏：滚动区铺满窗口高度 */
  const wh = Number(win.windowHeight) || 667
  scrollStyle.value = { height: `${Math.max(240, wh)}px` }
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
  } else {
    uni.switchTab({ url: '/pages/order/index' })
  }
}

onLoad((options) => {
  nextTick(() => {
    try {
      syncImmersionChrome()
    } catch {
      try {
        const win = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
        scrollStyle.value = { height: `${Math.max(240, win.windowHeight || 667)}px` }
      } catch {
        /* 保持默认 scrollStyle */
      }
    }
  })
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
  const mpRaw =
    (options && options.meal_period) ||
    (options && options.mealPeriod) ||
    ''
  const mp = mpRaw ? decodeURIComponent(String(mpRaw)).trim().toLowerCase() : ''
  mealPeriod.value = mp === MEAL_PERIOD_DINNER ? MEAL_PERIOD_DINNER : MEAL_PERIOD_LUNCH
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
    const d = await fetchMenuDetail(dishId, serviceDateYmd.value, mealPeriod.value)
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
  const block = singleOrderBlockReason(dish.value, serviceDateYmd.value)
  if (block) {
    uni.showToast({ title: block, icon: 'none' })
    return
  }
  const p = formatMenuPrice(dish.value.price)
  if (p == null) {
    uni.showToast({ title: '单点价格待公布', icon: 'none' })
    return
  }
  if (!getMemberToken()) {
    showOkAlert({
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
  const q = [`dish_id=${id}`, `service_date=${d}`]
  if (mealPeriod.value === MEAL_PERIOD_DINNER) {
    q.push(`meal_period=${encodeURIComponent(MEAL_PERIOD_DINNER)}`)
  }
  uni.navigateTo({
    url: `/packageOrder/pages/singleConfirm/singleConfirm?${q.join('&')}`,
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

/* 悬浮返回：盖在首张图上，半透明底避免亮色/暗色封面都看不清 */
.detail-float-back-hit {
  position: fixed;
  z-index: 1000;
  width: 88rpx;
  height: 88rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.62);
  border: 1rpx solid rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 12rpx 36rpx rgba(15, 23, 42, 0.14);
}

.detail-float-back-ico {
  font-size: 56rpx;
  font-weight: 950;
  color: #73B054;
  line-height: 1;
  padding-right: 4rpx;
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
  /* 沉浸式大图区域：更高、更醒目（仍随屏宽比例伸缩） */
  height: 88vw;
  max-height: 92vh;
  min-height: 440rpx;
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

.detail-spice-strip {
  margin-bottom: 24rpx;
  padding: 16rpx 24rpx;
  background: #fff7ed;
  border-radius: 20rpx;
  border: 1rpx solid #fed7aa;
}

.detail-spice-txt {
  font-size: 26rpx;
  font-weight: 850;
  color: #9a3412;
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

.day-stock-soldout {
  font-size: 32rpx;
  font-weight: 950;
  color: $ok-slate-400;
  letter-spacing: 4rpx;
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
  padding: 24rpx 32rpx;
  background: $ok-forest-green;
  color: #fff;
  border: none;
  border-radius: 40rpx;
  font-size: 28rpx;
  font-weight: 900;
  line-height: 1.35;
  margin-top: 48rpx;
  box-shadow: 0 16rpx 32rpx rgba(115, 176, 84, 0.18);
}

.btn-order-confirm::after {
  border: none;
}
</style>
