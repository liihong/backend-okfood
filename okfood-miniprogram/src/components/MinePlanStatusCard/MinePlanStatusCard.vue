<template>
  <view class="plan-card">
    <text class="plan-card__watermark">OK</text>

    <view class="plan-card__head">
      <view class="plan-card__pill">
        <text class="plan-card__pill-txt">OK 饭 自律计划</text>
      </view>
      <text v-if="planLabel" class="plan-card__plan-type">{{ planLabel }}</text>
    </view>

    <view class="plan-card__hero-row">
      <view class="plan-card__balance">
        <text class="plan-card__num">{{ remainingDisplay }}</text>
        <text class="plan-card__num-lab">剩余自律餐次</text>
      </view>
      <view class="plan-card__slant-wrap">
        <text
          :class="['plan-card__slant', { 'plan-card__slant--alert': statusAlert }]"
        >{{ statusText }}</text>
      </view>
    </view>

    <view v-if="showResumeChip" class="plan-card__chip-row">
      <view class="plan-card__chip" @tap.stop="$emit('resume')">
        <text class="plan-card__chip-txt">恢复配送</text>
      </view>
    </view>

    <text v-if="addressLine" class="plan-card__addr">{{ addressLine }}</text>

    <view class="plan-card__foot">
      <text class="plan-card__foot-left">{{ footerTagline }}</text>
      <text v-if="dailyUnitsText" class="plan-card__foot-right">{{ dailyUnitsText }}</text>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  remainingMeals: { type: Number, default: 0 },
  statusText: { type: String, default: '' },
  /** 与高亮状态文案（如待完善资料）配套的浅色强调 */
  statusAlert: { type: Boolean, default: false },
  footerTagline: { type: String, default: '' },
  planLabel: { type: String, default: '' },
  addressLine: { type: String, default: '' },
  dailyUnitsText: { type: String, default: '' },
  showResumeChip: { type: Boolean, default: false },
})

defineEmits(['resume'])

const remainingDisplay = computed(() =>
  Math.max(0, Math.floor(Number(props.remainingMeals) || 0)),
)
</script>

<style lang="scss" scoped>
.plan-card {
  position: relative;
  overflow: hidden;
  border-radius: 28rpx;
  padding: 28rpx 28rpx 24rpx;
  margin-bottom: 28rpx;
  background: linear-gradient(145deg, $ok-forest-green-dark 0%, $ok-forest-green 48%, #0a4d3a 100%);
  box-shadow: 0 20rpx 48rpx rgba(14, 90, 68, 0.38);
}

.plan-card__watermark {
  position: absolute;
  right: -16rpx;
  bottom: -36rpx;
  font-size: 200rpx;
  font-weight: 950;
  color: rgba(255, 255, 255, 0.06);
  line-height: 1;
  pointer-events: none;
}

.plan-card__head {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20rpx;
  margin-bottom: 28rpx;
}

.plan-card__pill {
  flex-shrink: 0;
  display: inline-flex;
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.18);
}

.plan-card__pill-txt {
  font-size: 22rpx;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.92);
}

.plan-card__hero-row {
  display: flex;
  flex-direction: row;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 8rpx;
}

.plan-card__balance {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: row;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 12rpx 16rpx;
}

.plan-card__num {
  font-size: 72rpx;
  font-weight: 950;
  color: #fff;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.plan-card__num-lab {
  font-size: 28rpx;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.9);
  line-height: 1.3;
}

.plan-card__slant-wrap {
  flex-shrink: 0;
  max-width: 42%;
  padding-bottom: 6rpx;
}

.plan-card__slant {
  display: block;
  font-size: 26rpx;
  font-weight: 900;
  color: rgba(180, 245, 200, 0.95);
  line-height: 1.35;
  text-align: right;
  transform: rotate(-8deg);
}

.plan-card__slant--alert {
  color: #fef08a;
}

.plan-card__chip-row {
  margin-top: 16rpx;
  margin-bottom: 4rpx;
}

.plan-card__chip {
  align-self: flex-start;
  display: inline-flex;
  padding: 10rpx 22rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.22);
}

.plan-card__chip-txt {
  font-size: 24rpx;
  font-weight: 900;
  color: #fff;
}

.plan-card__plan-type {
  flex-shrink: 0;
  max-width: 52%;
  text-align: right;
  font-size: 30rpx;
  font-weight: 900;
  color: rgba(254, 240, 138, 0.95);
  line-height: 1.25;
}

.plan-card__addr {
  display: block;
  margin-top: 12rpx;
  font-size: 22rpx;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.72);
  line-height: 1.45;
}

.plan-card__foot {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16rpx;
  margin-top: 22rpx;
  padding-top: 20rpx;
  border-top: 2rpx solid rgba(255, 255, 255, 0.14);
}

.plan-card__foot-left {
  flex: 1;
  min-width: 0;
  font-size: 22rpx;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.55);
  line-height: 1.45;
}

.plan-card__foot-right {
  flex-shrink: 0;
  font-size: 22rpx;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.65);
}
</style>
