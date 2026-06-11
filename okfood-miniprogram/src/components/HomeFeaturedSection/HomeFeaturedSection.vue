<template>
  <view class="home-featured">
    <view class="home-featured__head">
      <view class="home-featured__title-wrap">
        <text class="home-featured__star">✦</text>
       <text class="home-featured__title">今日推荐菜</text>
      </view>
      <text class="home-featured__more" @tap="goMenu">查看更多菜品 ›</text>
    </view>
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

function goMenu() {
  uni.switchTab({ url: '/pages/order/index' })
}
</script>

<style lang="scss" scoped>
.home-featured {
  padding: 0 32rpx 32rpx;
}

.home-featured__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.home-featured__title-wrap {
  display: flex;
  align-items: center;
  gap: 10rpx;
  min-width: 0;
}

.home-featured__star {
  flex-shrink: 0;
  font-size: 28rpx;
  color: #f97316;
  line-height: 1;
}

.home-featured__title {
  font-size: 30rpx;
  font-weight: 1000;
  color: #1e293b;
  line-height: 1.3;
}

.home-featured__more {
  flex-shrink: 0;
  font-size: 24rpx;
  font-weight: 600;
  color: $ok-slate-400;
  line-height: 1.3;
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
  box-shadow: 0 8rpx 32rpx rgba(15, 23, 42, 0.06);
}

.home-featured__state--muted {
  color: $ok-slate-400;
}
</style>
