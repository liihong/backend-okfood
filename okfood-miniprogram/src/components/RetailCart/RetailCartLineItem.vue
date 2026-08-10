<template>
  <view class="line" @tap.stop>
    <image v-if="item.coverImageUrl" class="line__img" :src="item.coverImageUrl" mode="aspectFill" />
    <view v-else class="line__img line__img--ph"><text>商</text></view>
    <view class="line__body">
      <text class="line__title">{{ item.title }}</text>
      <text v-if="stockHint" class="line__stock">{{ stockHint }}</text>
      <view class="line__foot">
        <text class="line__price">¥{{ priceText }}</text>
        <view class="line__qty">
          <view class="line__qty-btn" @tap.stop="emit('dec')">−</view>
          <text class="line__qty-num">{{ item.quantity }}</text>
          <view class="line__qty-btn line__qty-btn--plus" @tap.stop="emit('inc')">+</view>
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
  padding: 24rpx 0;
  border-bottom: 1rpx solid $ok-slate-100;
  box-sizing: border-box;
}

.line:last-child {
  border-bottom: none;
}

.line__img {
  width: 136rpx;
  height: 136rpx;
  border-radius: 16rpx;
  flex-shrink: 0;
  background: $ok-slate-50;
}

.line__img--ph {
  display: flex;
  align-items: center;
  justify-content: center;
  color: $ok-slate-400;
  font-size: 28rpx;
}

.line__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  overflow: hidden;
}

.line__title {
  font-size: 28rpx;
  color: $ok-slate-800;
  font-weight: 600;
  line-height: 1.35;
  /* 长标题省略，避免把右侧加减挤出可视区 */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.line__stock {
  font-size: 22rpx;
  color: $ok-slate-400;
  line-height: 1.3;
}

.line__foot {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding-top: 4rpx;
}

.line__price {
  flex-shrink: 0;
  font-size: 32rpx;
  color: #ea580c;
  font-weight: 700;
  line-height: 1.1;
}

.line__qty {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.line__qty-btn {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: $ok-slate-100;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30rpx;
  font-weight: 600;
  color: $ok-slate-700;
  line-height: 1;
}

.line__qty-btn--plus {
  background: $ok-forest-green;
  color: #fff;
}

.line__qty-num {
  min-width: 40rpx;
  text-align: center;
  font-size: 28rpx;
  font-weight: 600;
  color: $ok-slate-800;
}
</style>
