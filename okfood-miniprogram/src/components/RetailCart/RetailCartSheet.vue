<template>
  <view v-if="show" class="mask" @tap="close">
    <view class="sheet" @tap.stop>
      <view class="sheet__head">
        <text class="sheet__title">购物车</text>
        <text v-if="items.length" class="sheet__clear" @tap="onClear">清空</text>
      </view>
      <scroll-view scroll-y class="sheet__scroll" :show-scrollbar="false">
        <view v-if="!items.length" class="sheet__empty">购物车是空的，去加点商品吧</view>
        <RetailCartLineItem
          v-for="it in items"
          :key="it.retailProductId"
          :item="it"
          @inc="() => onInc(it)"
          @dec="() => onDec(it)"
        />
      </scroll-view>
      <view class="sheet__foot">
        <text class="sheet__total">合计 ¥ {{ subtotalText }}</text>
        <button class="sheet__btn" type="button" :disabled="!items.length" @tap="onCheckout">
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
  z-index: 200;
  background: rgba(15, 23, 42, 0.45);
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
  padding-bottom: env(safe-area-inset-bottom);
}

.sheet__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 32rpx 12rpx;
}

.sheet__title {
  font-size: 32rpx;
  font-weight: 700;
  color: #0f172a;
}

.sheet__clear {
  font-size: 26rpx;
  color: #64748b;
}

.sheet__scroll {
  flex: 1;
  min-height: 200rpx;
  max-height: 48vh;
  padding: 0 32rpx;
}

.sheet__empty {
  padding: 80rpx 0;
  text-align: center;
  color: #94a3b8;
  font-size: 28rpx;
}

.sheet__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  padding: 20rpx 32rpx 28rpx;
  border-top: 1rpx solid #f1f5f9;
}

.sheet__total {
  font-size: 30rpx;
  font-weight: 700;
  color: #0f172a;
}

.sheet__btn {
  margin: 0;
  padding: 0 40rpx;
  height: 80rpx;
  line-height: 80rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #f59e0b, #ea580c);
  color: #fff;
  font-size: 28rpx;
  font-weight: 600;
}

.sheet__btn[disabled] {
  opacity: 0.45;
}
</style>
