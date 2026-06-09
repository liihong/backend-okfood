<template>
  <view
    class="coupon-card"
    :class="{
      'coupon-card--selected': selected,
      'coupon-card--disabled': disabled,
      'coupon-card--compact': compact,
    }"
    @tap="onTap"
  >
    <view class="coupon-card__left">
      <view class="coupon-card__amount-wrap">
        <text class="coupon-card__currency">¥</text>
        <text class="coupon-card__amount">{{ discountDisplay }}</text>
      </view>
      <text v-if="minOrderHint" class="coupon-card__cond">{{ minOrderHint }}</text>
    </view>
    <view class="coupon-card__divider" />
    <view class="coupon-card__right">
      <view class="coupon-card__tag-row">
        <text class="coupon-card__tag">{{ bizTag }}</text>
        <text v-if="selected" class="coupon-card__check">✓</text>
      </view>
      <text class="coupon-card__title">{{ titleText }}</text>
      <text v-if="subText" class="coupon-card__sub" :lines="2">{{ subText }}</text>
      <text v-if="expiresText" class="coupon-card__exp">{{ expiresText }}</text>
    </view>
    <!-- 仅左侧票券缺口，右侧缺口在弹窗 overflow 下易被裁切 -->
    <view class="coupon-card__hole coupon-card__hole--tl" />
    <view class="coupon-card__hole coupon-card__hole--bl" />
  </view>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  coupon: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['select'])

const discountDisplay = computed(() => {
  const n = Number(props.coupon?.discount_yuan)
  if (!Number.isFinite(n)) return '—'
  return n % 1 === 0 ? String(Math.floor(n)) : n.toFixed(2)
})

const minOrderHint = computed(() => {
  const n = Number(props.coupon?.min_order_yuan)
  if (!Number.isFinite(n) || n <= 0) return '无门槛'
  return `满${n % 1 === 0 ? Math.floor(n) : n.toFixed(2)}可用`
})

const bizTag = computed(() => {
  const biz = String(props.coupon?.biz_type || '').trim()
  if (biz === 'single_meal') return '单餐'
  if (biz === 'store_retail') return '商城'
  return '购卡'
})

const titleText = computed(() => {
  const name = props.coupon?.template_name
  if (name && String(name).trim()) return String(name).trim()
  return '优惠券'
})

const subText = computed(() => {
  const hint = props.coupon?.usage_instructions
  if (hint && String(hint).trim()) return String(hint).trim()
  return ''
})

const expiresText = computed(() => {
  const raw = props.coupon?.expires_at
  if (!raw) return ''
  const s = String(raw).trim()
  if (s.length >= 10) return `有效期至 ${s.slice(0, 10)}`
  return ''
})

function onTap() {
  if (props.disabled) return
  emit('select', props.coupon)
}
</script>

<style lang="scss" scoped>
.coupon-card {
  position: relative;
  display: flex;
  align-items: stretch;
  width: 100%;
  box-sizing: border-box;
  min-height: 168rpx;
  border-radius: 20rpx;
  overflow: hidden;
  background: linear-gradient(135deg, #73B054 0%, #53833D 58%, #456D32 100%);
  box-shadow: 0 12rpx 32rpx rgba(83, 131, 61, 0.22);
}

.coupon-card--compact {
  min-height: 148rpx;
}

.coupon-card--compact .coupon-card__left {
  width: 168rpx;
  padding: 16rpx 8rpx;
}

.coupon-card--compact .coupon-card__hole--tl {
  left: 158rpx;
}

.coupon-card--compact .coupon-card__hole--bl {
  left: 158rpx;
}

.coupon-card--compact .coupon-card__right {
  padding: 18rpx 20rpx 18rpx 16rpx;
}

.coupon-card--compact .coupon-card__title {
  font-size: 26rpx;
}

.coupon-card--compact .coupon-card__sub,
.coupon-card--compact .coupon-card__exp {
  font-size: 20rpx;
}

.coupon-card--selected {
  box-shadow:
    0 0 0 3rpx rgba(250, 204, 21, 0.85),
    0 12rpx 32rpx rgba(83, 131, 61, 0.28);
}

.coupon-card--disabled {
  opacity: 0.55;
}

.coupon-card__left {
  width: 200rpx;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20rpx 12rpx;
}

.coupon-card__amount-wrap {
  display: flex;
  align-items: flex-end;
  color: #facc15;
  line-height: 1;
}

.coupon-card__currency {
  font-size: 28rpx;
  font-weight: 800;
  margin-right: 4rpx;
  margin-bottom: 8rpx;
}

.coupon-card__amount {
  font-size: 64rpx;
  font-weight: 900;
  letter-spacing: -2rpx;
}

.coupon-card--compact .coupon-card__amount {
  font-size: 56rpx;
}

.coupon-card__cond {
  margin-top: 10rpx;
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.78);
}

.coupon-card__divider {
  width: 0;
  border-left: 2rpx dashed rgba(255, 255, 255, 0.35);
  margin: 18rpx 0;
}

.coupon-card__right {
  flex: 1;
  width: 0;
  padding: 22rpx 28rpx 22rpx 16rpx;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  box-sizing: border-box;
  overflow: hidden;
}

.coupon-card__tag-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8rpx;
}

.coupon-card__tag {
  font-size: 20rpx;
  font-weight: 700;
  color: #064e3b;
  background: rgba(250, 204, 21, 0.95);
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
}

.coupon-card__check {
  font-size: 28rpx;
  color: #facc15;
  font-weight: 800;
}

.coupon-card__title {
  display: block;
  width: 100%;
  font-size: 30rpx;
  font-weight: 800;
  color: #fff;
  line-height: 1.35;
  word-break: break-all;
}

.coupon-card__sub {
  display: block;
  width: 100%;
  margin-top: 6rpx;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.82);
  line-height: 1.4;
  overflow: hidden;
  word-break: break-all;
}

.coupon-card__exp {
  display: block;
  width: 100%;
  margin-top: 8rpx;
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.65);
  word-break: break-all;
}

.coupon-card__hole {
  position: absolute;
  width: 20rpx;
  height: 20rpx;
  border-radius: 50%;
  background: #f8fafc;
}

.coupon-card__hole--tl {
  left: 190rpx;
  top: -10rpx;
}

.coupon-card__hole--bl {
  left: 190rpx;
  bottom: -10rpx;
}

</style>
