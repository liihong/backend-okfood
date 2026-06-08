<template>
  <view class="home-featured">
    <text class="home-featured__title">今日主推</text>
    <view v-if="loading" class="home-featured__state">加载中…</view>
    <view v-else-if="!dish" class="home-featured__state home-featured__state--muted">今日暂无排餐</view>
    <MenuDishCard
      v-else
      layout="featured"
      :item="dish"
      :show-day-label="false"
      :show-ingredients="true"
      @tap="emit('tap', dish)"
    />
  </view>
</template>

<script setup>
import MenuDishCard from '@/components/MenuDishCard/MenuDishCard.vue'

defineProps({
  dish: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['tap'])
</script>

<style lang="scss" scoped>
.home-featured {
  padding: 0 32rpx 32rpx;
}

.home-featured__title {
  display: block;
  font-size: 34rpx;
  font-weight: 1000;
  color: #1e293b;
  margin-bottom: 24rpx;
}

.home-featured__state {
  padding: 48rpx 20rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
  background: #fff;
  border-radius: 32rpx;
  border: 1px solid $ok-slate-100;
}

.home-featured__state--muted {
  color: $ok-slate-400;
}
</style>
