<template>
  <view v-if="templates.length" class="home-card-strip">
    <view class="home-card-strip__head">
      <view class="home-card-strip__title-wrap">
        <text class="home-card-strip__star">?</text>
        <text class="home-card-strip__title">??????</text>
      </view>
      <text class="home-card-strip__more" @tap="goList">???? ?</text>
    </view>

    <view
      v-if="templates.length <= 2"
      class="home-card-strip__row"
      :class="'home-card-strip__row--' + templates.length"
    >
      <view
        v-for="(t, idx) in templates"
        :key="t.id"
        class="home-card-strip__card"
        :class="['home-card-strip__card--' + paletteClass(idx)]"
        @tap="goDetail(t.id)"
      >
        <text class="home-card-strip__water">OK</text>
        <text class="home-card-strip__cap">MEMBER CARD</text>
        <text class="home-card-strip__name">{{ t.name }}</text>
        <view class="home-card-strip__foot">
          <text class="home-card-strip__meals">{{ t.meals_grant }} ??</text>
          <text class="home-card-strip__price">¥{{ priceOrDash(t.sale_price_yuan) }}</text>
        </view>
      </view>
    </view>
    <scroll-view
      v-else
      scroll-x
      class="home-card-strip__scroll"
      :show-scrollbar="false"
      enable-flex
    >
      <view class="home-card-strip__inner">
        <view
          v-for="(t, idx) in templates"
          :key="t.id"
          class="home-card-strip__card home-card-strip__card--scroll"
          :class="['home-card-strip__card--' + paletteClass(idx)]"
          @tap="goDetail(t.id)"
        >
          <text class="home-card-strip__water">OK</text>
          <text class="home-card-strip__cap">MEMBER CARD</text>
          <text class="home-card-strip__name">{{ t.name }}</text>
          <view class="home-card-strip__foot">
            <text class="home-card-strip__meals">{{ t.meals_grant }} ??</text>
            <text class="home-card-strip__price">¥{{ priceOrDash(t.sale_price_yuan) }}</text>
          </view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
defineProps({
  templates: { type: Array, default: () => [] },
})

function paletteClass(i) {
  const k = i % 3
  if (k === 0) return 'a'
  if (k === 1) return 'b'
  return 'c'
}

function priceOrDash(v) {
  if (v == null || v === '') return '?'
  return String(v)
}

function goDetail(id) {
  uni.navigateTo({
    url: `/packageUser/pages/membershipCardDetail/membershipCardDetail?templateId=${encodeURIComponent(String(id))}`,
  })
}

function goList() {
  uni.navigateTo({ url: '/packageUser/pages/membershipCardList/membershipCardList' })
}
</script>

<style lang="scss" scoped>
.home-card-strip {
  width: 100%;
  margin-bottom: 32rpx;
  box-sizing: border-box;
}

.home-card-strip__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding: 0 32rpx;
  margin-bottom: 20rpx;
  box-sizing: border-box;
}

.home-card-strip__title-wrap {
  display: flex;
  align-items: center;
  gap: 10rpx;
  min-width: 0;
}

.home-card-strip__star {
  flex-shrink: 0;
  font-size: 28rpx;
  color: #f97316;
  line-height: 1;
}

.home-card-strip__title {
  font-size: 34rpx;
  font-weight: 1000;
  color: #1e293b;
  line-height: 1.3;
}

.home-card-strip__more {
  flex-shrink: 0;
  font-size: 24rpx;
  font-weight: 600;
  color: $ok-slate-400;
  line-height: 1.3;
}

.home-card-strip__row {
  display: flex;
  flex-direction: row;
  gap: 20rpx;
  padding: 0 32rpx;
  box-sizing: border-box;
}

.home-card-strip__row--1 .home-card-strip__card {
  flex: 1;
  width: 100%;
}

.home-card-strip__row--2 .home-card-strip__card {
  flex: 1;
  width: 0;
  min-width: 0;
}

.home-card-strip__scroll {
  width: 100%;
}

.home-card-strip__inner {
  display: flex;
  flex-direction: row;
  gap: 20rpx;
  padding: 0 32rpx 4rpx;
  box-sizing: border-box;
}

.home-card-strip__card {
  position: relative;
  min-height: 176rpx;
  border-radius: 24rpx;
  padding: 24rpx 22rpx 20rpx;
  box-sizing: border-box;
  overflow: hidden;
  box-shadow: 0 10rpx 28rpx rgba(15, 23, 42, 0.12);
}

.home-card-strip__card--scroll {
  width: 520rpx;
  flex-shrink: 0;
}

.home-card-strip__card--a {
  background: linear-gradient(135deg, #73b054 0%, #456d32 55%, #365628 100%);
}

.home-card-strip__card--b {
  background: linear-gradient(135deg, #b8860b 0%, #d97706 45%, #92400e 100%);
}

.home-card-strip__card--c {
  background: linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 50%, #312e81 100%);
}

.home-card-strip__water {
  position: absolute;
  right: -8rpx;
  bottom: -24rpx;
  font-size: 120rpx;
  font-weight: 900;
  color: rgba(255, 255, 255, 0.08);
  line-height: 1;
  pointer-events: none;
}

.home-card-strip__cap {
  position: relative;
  z-index: 1;
  display: block;
  font-size: 16rpx;
  letter-spacing: 0.14em;
  color: rgba(255, 255, 255, 0.72);
  margin-bottom: 8rpx;
}

.home-card-strip__name {
  position: relative;
  z-index: 1;
  display: block;
  font-size: 28rpx;
  font-weight: 800;
  color: #fff;
  line-height: 1.35;
  margin-bottom: 20rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-card-strip__foot {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.2);
}

.home-card-strip__meals {
  font-size: 22rpx;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.88);
  flex-shrink: 0;
}

.home-card-strip__price {
  font-size: 34rpx;
  font-weight: 900;
  color: #fef08a;
  line-height: 1;
  flex-shrink: 0;
}
</style>
