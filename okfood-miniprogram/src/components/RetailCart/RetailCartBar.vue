<template>
  <view v-if="visible" class="retail-cart-bar" :style="barStyle" @tap="emit('open')">
    <view class="retail-cart-bar__left">
      <view class="retail-cart-bar__icon-wrap">
        <text class="retail-cart-bar__icon">🛒</text>
        <view v-if="count > 0" class="retail-cart-bar__badge">
          <text class="retail-cart-bar__badge-txt">{{ count > 99 ? '99+' : count }}</text>
        </view>
      </view>
      <view class="retail-cart-bar__info">
        <text class="retail-cart-bar__price">¥ {{ subtotalText }}</text>
        <text class="retail-cart-bar__hint">不含配送费说明以结算为准</text>
      </view>
    </view>
    <view class="retail-cart-bar__btn">
      <text class="retail-cart-bar__btn-txt">去结算</text>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  count: { type: Number, default: 0 },
  subtotalText: { type: String, default: '0.00' },
  /** tabBar 上方留白（px） */
  bottomOffsetPx: { type: Number, default: 52 },
})

const emit = defineEmits(['open'])

const barStyle = computed(() => ({
  bottom: `${Math.max(0, Number(props.bottomOffsetPx) || 0)}px`,
}))
</script>

<style lang="scss" scoped>
.retail-cart-bar {
  position: fixed;
  left: 24rpx;
  right: 24rpx;
  z-index: 120;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16rpx 20rpx 16rpx 24rpx;
  border-radius: 999rpx;
  background: #0f172a;
  box-shadow: 0 8rpx 32rpx rgba(15, 23, 42, 0.28);
}

.retail-cart-bar__left {
  display: flex;
  align-items: center;
  gap: 16rpx;
  min-width: 0;
}

.retail-cart-bar__icon-wrap {
  position: relative;
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
}

.retail-cart-bar__icon {
  font-size: 36rpx;
}

.retail-cart-bar__badge {
  position: absolute;
  top: -4rpx;
  right: -4rpx;
  min-width: 32rpx;
  height: 32rpx;
  padding: 0 8rpx;
  border-radius: 999rpx;
  background: #ef4444;
  display: flex;
  align-items: center;
  justify-content: center;
}

.retail-cart-bar__badge-txt {
  color: #fff;
  font-size: 20rpx;
  line-height: 1;
}

.retail-cart-bar__info {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
  min-width: 0;
}

.retail-cart-bar__price {
  color: #fff;
  font-size: 32rpx;
  font-weight: 700;
}

.retail-cart-bar__hint {
  color: rgba(255, 255, 255, 0.55);
  font-size: 20rpx;
}

.retail-cart-bar__btn {
  flex-shrink: 0;
  padding: 18rpx 36rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #f59e0b, #ea580c);
}

.retail-cart-bar__btn-txt {
  color: #fff;
  font-size: 28rpx;
  font-weight: 600;
}
</style>
