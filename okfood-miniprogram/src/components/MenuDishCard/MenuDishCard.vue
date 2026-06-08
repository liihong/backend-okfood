<template>
  <view
    class="menu-dish-card"
    :class="[
      layout === 'featured' ? 'menu-dish-card--featured' : 'menu-dish-card--grid',
    ]"
    @click="emit('tap', item)"
  >
    <view class="menu-dish-card__img-wrap">
      <text v-if="showDayLabel && item.day" class="menu-dish-card__day-tag">{{ item.day }}</text>
      <image
        class="menu-dish-card__img"
        :src="item.img"
        mode="aspectFill"
        @error="onImgErr"
      />
    </view>
    <view class="menu-dish-card__body">
      <view class="menu-dish-card__title-row">
        <text class="menu-dish-card__name">{{ item.name }}</text>
        <text v-if="item.spiceLabel" class="menu-dish-card__spice">{{ item.spiceLabel }}</text>
      </view>
      <view class="menu-dish-card__price-row">
        <text class="menu-dish-card__price-label">自律体验价</text>
        <text v-if="priceText != null" class="menu-dish-card__price">¥{{ priceText }}</text>
        <text v-else class="menu-dish-card__price menu-dish-card__price--pending">待公布</text>
      </view>
      <text v-if="layout === 'featured'" class="menu-dish-card__cta">立即购买 ›</text>
      <text v-if="showIngredients" class="menu-dish-card__ingredients">配料：{{ item.ingredients }}</text>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'
import { formatMenuPrice } from '@/utils/menuApi.js'

const props = defineProps({
  item: { type: Object, required: true },
  layout: { type: String, default: 'grid' },
  showDayLabel: { type: Boolean, default: true },
  showIngredients: { type: Boolean, default: true },
})

const emit = defineEmits(['tap'])

const priceText = computed(() => formatMenuPrice(props.item?.price))

const fallbackImg =
  'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400'

function onImgErr() {
  if (props.item && typeof props.item === 'object') {
    props.item.img = fallbackImg
  }
}
</script>

<style lang="scss" scoped>
.menu-dish-card {
  background: #fff;
  border-radius: 48rpx;
  overflow: hidden;
  border: 1px solid $ok-slate-100;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
}

.menu-dish-card--featured {
  flex-direction: row;
  align-items: stretch;
  min-height: 220rpx;
}

.menu-dish-card--featured .menu-dish-card__img-wrap {
  width: 220rpx;
  min-width: 220rpx;
  aspect-ratio: auto;
  height: auto;
  min-height: 220rpx;
}

.menu-dish-card--featured .menu-dish-card__body {
  flex: 1;
  justify-content: center;
}

.menu-dish-card__img-wrap {
  width: 100%;
  aspect-ratio: 1;
  background: $ok-slate-50;
  position: relative;
  overflow: hidden;
}

.menu-dish-card__img {
  width: 100%;
  height: 100%;
}

.menu-dish-card__day-tag {
  position: absolute;
  top: 20rpx;
  left: 20rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 24rpx;
  font-weight: 900;
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
  z-index: 10;
}

.menu-dish-card__body {
  padding: 24rpx;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.menu-dish-card__title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12rpx;
  margin-bottom: 4rpx;
}

.menu-dish-card__name {
  flex: 1;
  min-width: 0;
  font-size: 28rpx;
  font-weight: 950;
  color: #333;
}

.menu-dish-card--grid .menu-dish-card__name {
  font-size: 26rpx;
}

.menu-dish-card__spice {
  flex-shrink: 0;
  font-size: 18rpx;
  font-weight: 900;
  color: #9a3412;
  background: #fff7ed;
  border: 1rpx solid #fed7aa;
  padding: 4rpx 12rpx;
  border-radius: 12rpx;
  line-height: 1.3;
}

.menu-dish-card__price-row {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
  margin-bottom: 12rpx;
}

.menu-dish-card__price-label {
  font-size: 16rpx;
  color: $ok-slate-400;
  font-weight: 900;
}

.menu-dish-card__price {
  font-size: 32rpx;
  font-weight: 1000;
  font-style: italic;
  color: $ok-forest-green;
}

.menu-dish-card__price--pending {
  font-size: 26rpx;
  font-style: normal;
  font-weight: 800;
  color: $ok-slate-400;
}

.menu-dish-card__cta {
  font-size: 24rpx;
  font-weight: 900;
  color: $ok-forest-green;
  margin-bottom: 8rpx;
}

.menu-dish-card__ingredients {
  font-size: 18rpx;
  color: $ok-slate-400;
  line-height: 1.4;
  font-weight: 700;
  max-height: 2.8em;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
