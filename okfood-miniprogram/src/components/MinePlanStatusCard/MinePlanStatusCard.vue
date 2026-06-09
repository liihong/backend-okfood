<template>
  <view class="plan-card" :class="themeClass">
    <text class="plan-card__watermark">OK</text>

    <view v-if="planLabel" class="plan-card__vip-ribbon" :class="vipRibbonClass">
      <text class="plan-card__vip-ribbon-txt">{{ planLabel }}</text>
    </view>

    <view class="plan-card__head">
      <view class="plan-card__pill">
        <text class="plan-card__pill-txt">OK 饭 自律计划</text>
      </view>
    </view>

    <view class="plan-card__hero-row">
      <view class="plan-card__balance">
        <text class="plan-card__num">{{ remainingDisplay }}</text>
        <text class="plan-card__num-lab">剩余自律餐次</text>
      </view>
      <view v-if="statusText" class="plan-card__slant-wrap">
        <text
          class="plan-card__slant"
          :class="{
            'plan-card__slant--alert': statusAlert || isHeroStatusAlert,
            'plan-card__slant--active': isHeroStatusBreathe,
          }"
        >{{ statusText }}</text>
      </view>
    </view>

    <text
      v-if="addressLine"
      :class="['plan-card__addr', { 'plan-card__addr--alert': statusAlert }]"
    >{{ addressLine }}</text>

    <view class="plan-card__foot">
      <text class="plan-card__foot-left">{{ footerTagline }}</text>
      <view
        v-if="showResumeChip"
        class="plan-card__foot-resume"
        @tap.stop="$emit('resume')"
      >
        <text class="plan-card__foot-resume-txt">点我恢复配送</text>
      </view>
      <view
        v-else-if="showSetupDeliveryChip"
        class="plan-card__foot-resume"
        @tap.stop="$emit('setup-delivery')"
      >
        <text class="plan-card__foot-resume-txt">设置配送信息</text>
      </view>
      <view
        v-else-if="showBuyCardChip"
        class="plan-card__foot-resume"
        @tap.stop="$emit('buy-card')"
      >
        <text class="plan-card__foot-resume-txt">去购卡</text>
      </view>
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
  /** 周卡 / 月卡 / 次卡，用于卡片配色 */
  planKind: { type: String, default: '' },
  addressLine: { type: String, default: '' },
  showResumeChip: { type: Boolean, default: false },
  /** 待完善配送信息时展示「设置配送信息」按钮 */
  showSetupDeliveryChip: { type: Boolean, default: false },
  /** 无剩余餐次时展示「去购卡」按钮 */
  showBuyCardChip: { type: Boolean, default: false },
})

defineEmits(['resume', 'buy-card', 'setup-delivery'])

const remainingDisplay = computed(() =>
  Math.max(0, Math.floor(Number(props.remainingMeals) || 0)),
)

/** 请假、暂停时用高亮色强调 */
const isHeroStatusAlert = computed(() => {
  const t = String(props.statusText || '')
  return t.includes('请假') || t.includes('暂停配送')
})

/** 正常配送中 / 请假：右上角状态呼吸灯高亮 */
const isHeroStatusBreathe = computed(() => {
  if (props.statusAlert || props.showResumeChip || props.showSetupDeliveryChip) return false
  const s = String(props.statusText || '').trim()
  if (!s) return false
  return s.includes('正常配送') || s.includes('请假') || s.includes('暂停配送')
})

const themeClass = computed(() => {
  const p = String(props.planKind || '').trim()
  if (p === '月卡') return 'plan-card--month'
  if (p === '次卡') return 'plan-card--times'
  return 'plan-card--week'
})

/** 会员角标样式：周卡 / 月卡 / 次卡 */
const vipRibbonClass = computed(() => {
  const p = String(props.planKind || '').trim()
  if (p === '月卡') return 'plan-card__vip-ribbon--month'
  if (p === '次卡') return 'plan-card__vip-ribbon--times'
  return 'plan-card__vip-ribbon--week'
})
</script>

<style lang="scss" scoped>
.plan-card {
  position: relative;
  overflow: hidden;
  border-radius: 28rpx;
  padding: 28rpx 28rpx 24rpx;
  margin-bottom: 28rpx;
}

.plan-card--week {
  background: linear-gradient(145deg, $ok-forest-green-dark 0%, $ok-forest-green 48%, $ok-forest-green-darker 100%);
  box-shadow: 0 20rpx 48rpx rgba(115, 176, 84, 0.38);
}

.plan-card--month {
  background: linear-gradient(135deg, #b8860b 0%, #d97706 45%, #92400e 100%);
  box-shadow: 0 20rpx 48rpx rgba(146, 64, 14, 0.38);

  .plan-card__slant,
  .plan-card__addr,
  .plan-card__foot-left,
  .plan-card__foot-right {
    color: rgba(255, 248, 220, 0.95);
  }
}

.plan-card--times {
  background: linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 50%, #312e81 100%);
  box-shadow: 0 20rpx 48rpx rgba(30, 58, 95, 0.38);

  .plan-card__slant,
  .plan-card__addr,
  .plan-card__foot-left,
  .plan-card__foot-right {
    color: rgba(191, 219, 254, 0.95);
  }
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
  margin-bottom: 28rpx;
  padding-right: 120rpx;
}

/** 右上角斜角 VIP 会员标 */
.plan-card__vip-ribbon {
  position: absolute;
  top: 22rpx;
  right: -36rpx;
  z-index: 3;
  width: 220rpx;
  padding: 10rpx 0;
  transform: rotate(32deg);
  transform-origin: center center;
  text-align: center;
  border-radius: 6rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.28);
  animation: plan-card-vip-glow 3s ease-in-out infinite;
}

.plan-card__vip-ribbon--week {
  background: linear-gradient(135deg, #fef9c3 0%, #fde047 42%, #facc15 100%);
  border: 2rpx solid rgba(255, 255, 255, 0.55);
}

.plan-card__vip-ribbon--month {
  background: linear-gradient(135deg, #fff7ed 0%, #fed7aa 50%, #fb923c 100%);
  border: 2rpx solid rgba(255, 255, 255, 0.6);
}

.plan-card__vip-ribbon--times {
  background: linear-gradient(135deg, #e0f2fe 0%, #93c5fd 50%, #6366f1 100%);
  border: 2rpx solid rgba(255, 255, 255, 0.55);
}

.plan-card__vip-ribbon-txt {
  display: block;
  font-size: 22rpx;
  font-weight: 950;
  letter-spacing: 3rpx;
  white-space: nowrap;
}

.plan-card__vip-ribbon--week .plan-card__vip-ribbon-txt {
  color: #14532d;
}

.plan-card__vip-ribbon--month .plan-card__vip-ribbon-txt {
  color: #7c2d12;
}

.plan-card__vip-ribbon--times .plan-card__vip-ribbon-txt {
  color: #1e3a8a;
}

@keyframes plan-card-vip-glow {
  0%,
  100% {
    box-shadow: 0 8rpx 20rpx rgba(0, 0, 0, 0.22);
  }
  50% {
    box-shadow:
      0 10rpx 28rpx rgba(0, 0, 0, 0.28),
      0 0 24rpx rgba(254, 240, 138, 0.45);
  }
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
}

.plan-card__slant--alert {
  color: #fef08a;
}

.plan-card__slant--active {
  animation: plan-card-foot-breathe 2.2s ease-in-out infinite;
  padding: 8rpx 14rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.2);
}

/** 底部操作：恢复配送、设置配送信息等呼吸灯 */
.plan-card__foot-resume {
  flex-shrink: 0;
  display: inline-flex;
  padding: 8rpx 18rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.2);
  animation: plan-card-foot-breathe 2.2s ease-in-out infinite;
}

@keyframes plan-card-foot-breathe {
  0%,
  100% {
    background: rgba(255, 255, 255, 0.2);
    box-shadow:
      0 0 0 0 rgba(254, 240, 138, 0.35),
      0 0 12rpx 0 rgba(254, 240, 138, 0.15);
    transform: scale(1);
  }
  50% {
    background: rgba(255, 255, 255, 0.38);
    box-shadow:
      0 0 0 6rpx rgba(254, 240, 138, 0.28),
      0 0 28rpx 6rpx rgba(254, 240, 138, 0.55);
    transform: scale(1.03);
  }
}

.plan-card__foot-resume-txt {
  font-size: 22rpx;
  font-weight: 900;
  color: #fff;
  line-height: 1.35;
  white-space: nowrap;
}

.plan-card__addr {
  display: block;
  margin-top: 12rpx;
  font-size: 22rpx;
  font-weight: 800;
  color: rgba(180, 245, 200, 0.95);
  line-height: 1.45;
  word-break: break-all;
  white-space: normal;
}

.plan-card__addr--alert {
  color: #fef08a;
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
  font-weight: 800;
  color: rgba(180, 245, 200, 0.95);
  line-height: 1.45;
}

.plan-card__foot-right {
  font-size: 22rpx;
  font-weight: 900;
  color: rgba(180, 245, 200, 0.95);
  line-height: 1.35;
  white-space: nowrap;
}
</style>
