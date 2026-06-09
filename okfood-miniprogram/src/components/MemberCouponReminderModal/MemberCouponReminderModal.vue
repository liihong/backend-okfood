<template>
  <view v-if="visible" class="reminder-mask" @tap="onDismiss">
    <view class="reminder-panel" @tap.stop>
      <view class="reminder-glow" />
      <view class="reminder-head">
        <text class="reminder-kicker">VIP 专属福利</text>
        <text class="reminder-title">您有优惠券待使用</text>
        <text class="reminder-desc">{{ descLine }}</text>
      </view>

      <scroll-view
        v-if="coupons.length"
        scroll-y
        class="reminder-scroll"
        :show-scrollbar="false"
      >
        <view class="reminder-cards">
          <view v-for="c in coupons" :key="c.id" class="reminder-card-wrap">
            <MemberCouponCard :coupon="c" compact />
          </view>
        </view>
      </scroll-view>

      <view class="reminder-actions">
        <view class="reminder-btn reminder-btn--ghost" @tap="onDismiss">
          <text>稍后再说</text>
        </view>
        <view class="reminder-btn reminder-btn--primary" @tap="onConfirm">
          <text>去购卡使用</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'
import MemberCouponCard from '@/components/MemberCouponCard/MemberCouponCard.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  count: { type: Number, default: 0 },
  maxDiscountYuan: { type: String, default: '' },
  coupons: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:visible', 'confirm', 'dismiss'])

const maxDiscountDisplay = computed(() => {
  const n = Number(props.maxDiscountYuan)
  if (!Number.isFinite(n) || n <= 0) return '0'
  return n % 1 === 0 ? String(Math.floor(n)) : n.toFixed(2)
})

const descLine = computed(() => {
  const disc = maxDiscountDisplay.value
  const n = Math.max(0, Math.floor(Number(props.count) || 0))
  if (disc && disc !== '0') {
    return `您有 ${n} 张购卡券可用，开卡最高可减 ¥${disc}`
  }
  return `您有 ${n} 张购卡券可用，开卡时可自动抵扣`
})

function onDismiss() {
  emit('update:visible', false)
  emit('dismiss')
}

function onConfirm() {
  emit('update:visible', false)
  emit('confirm')
}
</script>

<style lang="scss" scoped>
.reminder-mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48rpx 36rpx;
  background: rgba(15, 23, 42, 0.55);
}

.reminder-panel {
  position: relative;
  width: 100%;
  max-width: 640rpx;
  border-radius: 28rpx;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 24rpx 64rpx rgba(15, 23, 42, 0.2);
}

.reminder-glow {
  position: absolute;
  left: -20%;
  right: -20%;
  top: -120rpx;
  height: 240rpx;
  background: radial-gradient(ellipse at center, rgba(16, 185, 129, 0.28), transparent 70%);
  pointer-events: none;
}

.reminder-head {
  position: relative;
  padding: 40rpx 36rpx 24rpx;
  text-align: center;
}

.reminder-kicker {
  display: block;
  font-size: 22rpx;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #73B054;
  margin-bottom: 12rpx;
}

.reminder-title {
  display: block;
  font-size: 40rpx;
  font-weight: 900;
  color: #1e293b;
  line-height: 1.25;
}

.reminder-desc {
  display: block;
  margin-top: 14rpx;
  font-size: 26rpx;
  color: #64748b;
  line-height: 1.5;
}

.reminder-desc--hl {
  color: #73B054;
  font-weight: 800;
}

.reminder-scroll {
  width: 100%;
  max-height: 420rpx;
  padding: 0 32rpx 12rpx;
  box-sizing: border-box;
}

.reminder-cards {
  width: 100%;
  box-sizing: border-box;
  padding-bottom: 8rpx;
}

.reminder-card-wrap {
  width: 100%;
  box-sizing: border-box;
}

.reminder-card-wrap + .reminder-card-wrap {
  margin-top: 20rpx;
}

.reminder-actions {
  display: flex;
  padding: 28rpx 28rpx 36rpx;
}

.reminder-actions .reminder-btn + .reminder-btn {
  margin-left: 20rpx;
}

.reminder-btn {
  flex: 1;
  height: 88rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
  font-weight: 700;
}

.reminder-btn--ghost {
  background: #f1f5f9;
  color: #475569;
}

.reminder-btn--primary {
  background: linear-gradient(135deg, #73B054, #53833D);
  color: #fff;
  box-shadow: 0 10rpx 24rpx rgba(83, 131, 61, 0.28);
}
</style>
