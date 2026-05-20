<template>
  <view class="page">
    <OkNavbar show-back title="自律膳食卡包" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
     <view class="wrap">

        <view v-if="loading" class="state-box">
          <text class="state-txt">加载卡包中…</text>
        </view>
        <view v-else-if="!items.length" class="state-box">
          <text class="state-txt">暂无卡包，请联系门店配置</text>
        </view>

        <view
          v-for="(t, idx) in items"
          :key="t.id"
          class="card-tap"
          @tap="goDetail(t.id)"
        >
          <view class="mcard" :class="['mcard--' + paletteClass(idx)]">
            <view class="mcard-water">OK</view>
            <view class="mcard-top">
              <view class="mcard-brand">
                <text class="mcard-cap">OK MEAL MEMBER CARD</text>
                <text class="mcard-name">{{ t.name }}</text>
              </view>
              <view class="mcard-pill"><text class="mcard-pill-txt">VIP 专享</text></view>
            </view>
            <view class="mcard-mid">
              <text class="mcard-fit">FITNESS LIFE</text>
            </view>
            <view class="mcard-foot">
              <view>
                <text class="mcard-lab">可享总餐次</text>
                <text class="mcard-val">{{ t.meals_grant }} 次餐</text>
              </view>
              <view class="mcard-price-block">
                <text class="mcard-lab">特惠价格</text>
                <view class="mcard-price-row">
                  <text v-if="t.list_price_yuan" class="mcard-list">¥{{ t.list_price_yuan }}</text>
                  <text class="mcard-sale">¥{{ priceOrDash(t.sale_price_yuan) }}</text>
                </view>
              </view>
            </view>
          </view>
        </view>

        <view class="rules">
          <view class="rules-head">
            <text class="rules-ico">🛡️</text>
            <text class="rules-title">购卡与配送规则说明</text>
          </view>
          <text class="rules-li">· 购买后，可在「我的」页面直接查收并激活自律餐次。</text>
          <text class="rules-li">· OK饭提供中心城区全程顺丰免配直发。</text>
          <text class="rules-li">· 餐次不设过期限制，可根据行程在系统内随时请假停配。</text>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getNavbarLayout } from '@/utils/navbar.js'
import { request, getMemberToken, clearMemberSession, isUserMeNotFoundError } from '@/utils/api.js'

const scrollStyle = ref({})
const loading = ref(true)
const items = ref([])

function paletteClass(i) {
  const k = i % 3
  if (k === 0) return 'a'
  if (k === 1) return 'b'
  return 'c'
}

function panSuffix(id) {
  const s = String(id ?? '0000').padStart(4, '0')
  return s.slice(-4)
}

function priceOrDash(v) {
  if (v == null || v === '') return '—'
  return String(v)
}

async function loadList() {
  if (!getMemberToken()) {
    loading.value = false
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 400)
    return
  }
  loading.value = true
  try {
    const data = await request('/api/user/membership-card-templates', { method: 'GET', retry: 1 })
    items.value = Array.isArray(data) ? data : []
  } catch (e) {
    if (isUserMeNotFoundError(e)) clearMemberSession()
    uni.showToast({ title: e instanceof Error ? e.message : '加载失败', icon: 'none' })
    items.value = []
  } finally {
    loading.value = false
  }
}

function goDetail(id) {
  uni.navigateTo({
    url: `/packageUser/pages/membershipCardDetail/membershipCardDetail?templateId=${encodeURIComponent(String(id))}`,
  })
}

onShow(() => {
  const { navBarTotal } = getNavbarLayout()
  scrollStyle.value = { height: `calc(100vh - ${navBarTotal}px)` }
  void loadList()
})
</script>

<style lang="scss" scoped>
.page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: $ok-slate-50;
  box-sizing: border-box;
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
}

.wrap {
  padding: 28rpx 32rpx calc(40rpx + env(safe-area-inset-bottom));
}

.hero {
  margin-bottom: 28rpx;
}

.hero-pill {
  display: inline-block;
  font-size: 20rpx;
  letter-spacing: 0.12em;
  color: $ok-forest-green;
  background: rgba(16, 185, 129, 0.15);
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
  margin-bottom: 16rpx;
}

.hero-title {
  display: block;
  font-size: 40rpx;
  font-weight: 800;
  color: $ok-slate-800;
  line-height: 1.25;
  margin-bottom: 12rpx;
}

.hero-sub {
  display: block;
  font-size: 26rpx;
  color: $ok-slate-500;
  line-height: 1.45;
}

.state-box {
  padding: 48rpx 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.state-txt {
  font-size: 28rpx;
  color: $ok-slate-500;
}

.card-tap {
  margin-bottom: 28rpx;
}

.mcard {
  position: relative;
  border-radius: 28rpx;
  padding: 32rpx 28rpx 28rpx;
  overflow: hidden;
  box-shadow: 0 16rpx 40rpx rgba(15, 23, 42, 0.12);
}

.mcard--a {
  background: linear-gradient(135deg, #0e5a44 0%, #0b4334 55%, #052e24 100%);
}
.mcard--b {
  background: linear-gradient(135deg, #b8860b 0%, #d97706 45%, #92400e 100%);
}
.mcard--c {
  background: linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 50%, #312e81 100%);
}

.mcard-water {
  position: absolute;
  right: -20rpx;
  bottom: -32rpx;
  font-size: 160rpx;
  font-weight: 900;
  color: rgba(255, 255, 255, 0.08);
  line-height: 1;
  pointer-events: none;
}

.mcard-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  position: relative;
  z-index: 1;
}

.mcard-brand {
  flex: 1;
  min-width: 0;
}

.mcard-cap {
  display: block;
  font-size: 18rpx;
  letter-spacing: 0.14em;
  color: rgba(255, 255, 255, 0.72);
  margin-bottom: 10rpx;
}

.mcard-name {
  display: block;
  font-size: 30rpx;
  font-weight: 700;
  color: #fff;
  line-height: 1.35;
}

.mcard-pill {
  flex-shrink: 0;
  margin-left: 16rpx;
  padding: 8rpx 18rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.18);
}

.mcard-pill-txt {
  font-size: 22rpx;
  color: #fff;
}

.mcard-mid {
  position: relative;
  z-index: 1;
  margin-top: 28rpx;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}

.mcard-pan {
  font-size: 26rpx;
  letter-spacing: 0.06em;
  color: rgba(255, 255, 255, 0.92);
  font-family: ui-monospace, monospace;
}

.mcard-fit {
  font-size: 18rpx;
  letter-spacing: 0.2em;
  color: rgba(255, 255, 255, 0.55);
}

.mcard-foot {
  position: relative;
  z-index: 1;
  margin-top: 36rpx;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding-top: 24rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.22);
}

.mcard-lab {
  display: block;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 8rpx;
}

.mcard-val {
  font-size: 34rpx;
  font-weight: 700;
  color: #fff;
}

.mcard-price-block {
  text-align: right;
}

.mcard-price-row {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 12rpx;
}

.mcard-list {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.55);
  text-decoration: line-through;
}

.mcard-sale {
  font-size: 40rpx;
  font-weight: 800;
  color: #fef08a;
}

.rules {
  margin-top: 12rpx;
  background: #fff;
  border-radius: 24rpx;
  padding: 28rpx 28rpx 32rpx;
  box-shadow: 0 8rpx 24rpx rgba(15, 23, 42, 0.06);
}

.rules-head {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.rules-ico {
  font-size: 32rpx;
}

.rules-title {
  font-size: 30rpx;
  font-weight: 700;
  color: $ok-slate-800;
}

.rules-li {
  display: block;
  font-size: 26rpx;
  color: $ok-slate-600;
  line-height: 1.55;
  margin-bottom: 12rpx;
}
</style>
