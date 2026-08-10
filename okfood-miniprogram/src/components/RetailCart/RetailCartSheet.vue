<template>
  <!-- z-index 需高于自定义 tabBar(9999)，避免底部结算区被遮挡 -->
  <view v-if="show" class="mask" @tap="close">
    <view class="sheet" @tap.stop>
      <view class="sheet__handle-wrap">
        <view class="sheet__handle" />
      </view>
      <view class="sheet__head">
        <text class="sheet__title">购物车</text>
        <view v-if="items.length" class="sheet__clear" @tap="onClear">
          <text class="sheet__clear-txt">清空</text>
        </view>
      </view>
      <scroll-view scroll-y class="sheet__scroll" :show-scrollbar="false">
        <!-- scroll-view 自身 padding 在小程序端易失效，内层包一层 -->
        <view class="sheet__list">
          <view v-if="!items.length" class="sheet__empty">购物车是空的，去加点商品吧</view>
          <RetailCartLineItem
            v-for="it in items"
            :key="it.retailProductId"
            :item="it"
            @inc="() => onInc(it)"
            @dec="() => onDec(it)"
          />
        </view>
      </scroll-view>
      <view class="sheet__foot">
        <view class="sheet__total-wrap">
          <text class="sheet__total-label">合计</text>
          <text class="sheet__total">¥{{ subtotalText }}</text>
        </view>
        <button
          class="sheet__btn"
          type="default"
          hover-class="none"
          :disabled="!items.length"
          @tap="onCheckout"
        >
          去结算
        </button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'
import RetailCartLineItem from './RetailCartLineItem.vue'
import {
  clearCart,
  setCartItemQuantity,
  addCartItem,
  getCartSubtotalText,
} from '@/utils/retailCart/retailCartStorage.js'
import { notifyRetailCartChanged } from '@/utils/retailCart/useRetailCart.js'

const props = defineProps({
  show: { type: Boolean, default: false },
  items: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:show', 'checkout'])

const subtotalText = computed(() => getCartSubtotalText())

function close() {
  emit('update:show', false)
}

function onClear() {
  uni.showModal({
    title: '清空购物车',
    content: '确定清空全部商品吗？',
    success(res) {
      if (!res.confirm) return
      clearCart()
      notifyRetailCartChanged()
    },
  })
}

function onInc(it) {
  const res = addCartItem(it, 1)
  notifyRetailCartChanged()
  if (!res.ok && res.msg) {
    uni.showToast({ title: res.msg, icon: 'none' })
  }
}

function onDec(it) {
  const q = (Number(it.quantity) || 1) - 1
  const res = setCartItemQuantity(it.retailProductId, q)
  notifyRetailCartChanged()
  if (res?.msg) {
    uni.showToast({ title: res.msg, icon: 'none' })
  }
}

function onCheckout() {
  if (!props.items.length) return
  emit('checkout')
  emit('update:show', false)
}
</script>

<style lang="scss" scoped>
.mask {
  position: fixed;
  inset: 0;
  z-index: 10050;
  background: rgba(15, 23, 42, 0.48);
  display: flex;
  align-items: flex-end;
}

.sheet {
  width: 100%;
  max-height: 72vh;
  background: #fff;
  border-radius: 28rpx 28rpx 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 -8rpx 40rpx rgba(15, 23, 42, 0.12);
  /* 覆盖 tabBar 后仍保留底部安全区 */
  padding-bottom: env(safe-area-inset-bottom);
}

.sheet__handle-wrap {
  display: flex;
  justify-content: center;
  padding: 16rpx 0 4rpx;
}

.sheet__handle {
  width: 64rpx;
  height: 8rpx;
  border-radius: 999rpx;
  background: #e2e8f0;
}

.sheet__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8rpx 32rpx 16rpx;
}

.sheet__title {
  font-size: 32rpx;
  font-weight: 700;
  color: $ok-slate-800;
}

.sheet__clear {
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
  background: $ok-slate-50;
}

.sheet__clear-txt {
  font-size: 24rpx;
  color: $ok-slate-500;
  line-height: 1.2;
}

.sheet__scroll {
  flex: 1;
  min-height: 200rpx;
  max-height: 48vh;
}

.sheet__list {
  padding: 0 32rpx 8rpx;
  box-sizing: border-box;
}

.sheet__empty {
  padding: 80rpx 0;
  text-align: center;
  color: $ok-slate-400;
  font-size: 28rpx;
}

.sheet__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  padding: 20rpx 32rpx 28rpx;
  border-top: 1rpx solid $ok-slate-100;
  background: #fff;
}

.sheet__total-wrap {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
  min-width: 0;
}

.sheet__total-label {
  font-size: 26rpx;
  color: $ok-slate-500;
  flex-shrink: 0;
}

.sheet__total {
  font-size: 36rpx;
  font-weight: 700;
  color: #ea580c;
  line-height: 1.1;
}

.sheet__btn {
  flex-shrink: 0;
  margin: 0;
  padding: 0 48rpx;
  height: 80rpx;
  line-height: 80rpx;
  border: none;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #f59e0b, #ea580c);
  color: #fff;
  font-size: 28rpx;
  font-weight: 600;
}

.sheet__btn::after {
  border: none;
}

.sheet__btn[disabled] {
  opacity: 0.45;
}
</style>
