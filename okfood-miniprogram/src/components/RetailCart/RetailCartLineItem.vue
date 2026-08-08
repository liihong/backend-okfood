<template>
  <view class="line" @tap.stop>
    <image v-if="item.coverImageUrl" class="line__img" :src="item.coverImageUrl" mode="aspectFill" />
    <view v-else class="line__img line__img--ph"><text>商</text></view>
    <view class="line__body">
      <text class="line__title">{{ item.title }}</text>
      <text v-if="stockHint" class="line__stock">{{ stockHint }}</text>
      <view class="line__foot">
        <text class="line__price">¥ {{ priceText }}</text>
        <view class="line__qty">
          <view class="line__qty-btn" @tap.stop="emit('dec')">−</view>
          <text class="line__qty-num">{{ item.quantity }}</text>
          <view class="line__qty-btn" @tap.stop="emit('inc')">+</view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
})

const emit = defineEmits(['inc', 'dec'])

const priceText = computed(() => {
  const p = Number(props.item?.unitPriceYuan)
  return Number.isFinite(p) ? p.toFixed(2) : '—'
})

const stockHint = computed(() => {
  const it = props.item || {}
  const sold = Number(it.soldCount) || 0
  const soldTxt = sold > 0 ? `已售${sold}` : ''
  if (!it.stockLimited) return soldTxt
  const remain = it.stockRemaining
  const remainTxt = remain != null ? `剩 ${remain} 件` : ''
  return [soldTxt, remainTxt].filter(Boolean).join(' · ')
})
</script>

<style lang="scss" scoped>
.line {
  display: flex;
  gap: 20rpx;
  padding: 20rpx 0;
  border-bottom: 1rpx solid #f1f5f9;
}

.line__img {
  width: 128rpx;
  height: 128rpx;
  border-radius: 16rpx;
  flex-shrink: 0;
  background: #f8fafc;
}

.line__img--ph {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 28rpx;
}

.line__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.line__title {
  font-size: 28rpx;
  color: #0f172a;
  font-weight: 600;
}

.line__stock {
  font-size: 22rpx;
  color: #64748b;
}

.line__foot {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.line__price {
  font-size: 30rpx;
  color: #ea580c;
  font-weight: 700;
}

.line__qty {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.line__qty-btn {
  width: 48rpx;
  height: 48rpx;
  border-radius: 12rpx;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
  color: #334155;
}

.line__qty-num {
  min-width: 36rpx;
  text-align: center;
  font-size: 28rpx;
}
</style>
