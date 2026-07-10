<template>
  <view class="retail-order-card">
    <text v-if="title" class="retail-order-card__title">{{ title }}</text>
    <slot />
  </view>
</template>

<script setup>
defineProps({
  /** 卡片标题，可选 */
  title: {
    type: String,
    default: '',
  },
})
</script>

<style lang="scss" scoped>
.retail-order-card {
  background: #fff;
  border-radius: 20rpx;
  padding: 28rpx;
  margin-bottom: 20rpx;
}

.retail-order-card__title {
  display: block;
  margin-bottom: 8rpx;
  font-size: 26rpx;
  font-weight: 800;
  color: #64748b;
}
</style>
