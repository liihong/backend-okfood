<template>
  <view v-if="visible" class="ok-alert-mask" @tap="onMaskTap">
    <view class="ok-alert-panel" @tap.stop>
      <view class="ok-alert-glow" :class="glowClass" />
      <view v-if="tone !== 'default'" class="ok-alert-icon-wrap">
        <view class="ok-alert-icon" :class="iconClass">
          <text class="ok-alert-icon-txt">{{ iconChar }}</text>
        </view>
      </view>
      <view class="ok-alert-body">
        <text v-if="title" class="ok-alert-title">{{ title }}</text>
        <text v-if="content" class="ok-alert-content">{{ content }}</text>
      </view>
      <view class="ok-alert-actions" :class="{ 'ok-alert-actions--single': !showCancel }">
        <view
          v-if="showCancel"
          class="ok-alert-btn ok-alert-btn--ghost"
          hover-class="ok-alert-btn--hover"
          @tap="onCancel"
        >
          <text>{{ cancelText }}</text>
        </view>
        <view
          class="ok-alert-btn"
          :class="confirmBtnClass"
          hover-class="ok-alert-btn--hover"
          @tap="onConfirm"
        >
          <text>{{ confirmText }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  content: { type: String, default: '' },
  showCancel: { type: Boolean, default: true },
  cancelText: { type: String, default: '取消' },
  confirmText: { type: String, default: '确定' },
  confirmDanger: { type: Boolean, default: false },
  tone: { type: String, default: 'default' },
  maskClosable: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel', 'mask'])

const glowClass = computed(() => {
  if (props.tone === 'success') return 'ok-alert-glow--success'
  if (props.tone === 'warning') return 'ok-alert-glow--warning'
  return ''
})

const iconClass = computed(() => {
  if (props.tone === 'success') return 'ok-alert-icon--success'
  if (props.tone === 'warning') return 'ok-alert-icon--warning'
  return ''
})

const iconChar = computed(() => {
  if (props.tone === 'success') return '✓'
  if (props.tone === 'warning') return '!'
  return ''
})

const confirmBtnClass = computed(() => {
  if (props.confirmDanger) return 'ok-alert-btn--danger'
  return 'ok-alert-btn--primary'
})

function onConfirm() {
  emit('confirm')
}

function onCancel() {
  emit('cancel')
}

function onMaskTap() {
  if (!props.maskClosable) return
  emit('mask')
  emit('cancel')
}
</script>

<style lang="scss" scoped>
.ok-alert-mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48rpx 40rpx;
  background: rgba(15, 23, 42, 0.52);
}

.ok-alert-panel {
  position: relative;
  width: 100%;
  max-width: 600rpx;
  border-radius: 32rpx;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 28rpx 72rpx rgba(15, 23, 42, 0.22);
}

.ok-alert-glow {
  position: absolute;
  left: -25%;
  right: -25%;
  top: -140rpx;
  height: 260rpx;
  background: radial-gradient(ellipse at center, rgba(148, 163, 184, 0.2), transparent 72%);
  pointer-events: none;
}

.ok-alert-glow--success {
  background: radial-gradient(ellipse at center, rgba(16, 185, 129, 0.32), transparent 72%);
}

.ok-alert-glow--warning {
  background: radial-gradient(ellipse at center, rgba(250, 204, 21, 0.28), transparent 72%);
}

.ok-alert-icon-wrap {
  position: relative;
  display: flex;
  justify-content: center;
  padding-top: 44rpx;
}

.ok-alert-icon {
  width: 96rpx;
  height: 96rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ok-alert-icon--success {
  background: linear-gradient(135deg, #ecfdf5, #d1fae5);
  border: 2rpx solid rgba(16, 185, 129, 0.35);
}

.ok-alert-icon--warning {
  background: linear-gradient(135deg, #fffbeb, #fef3c7);
  border: 2rpx solid rgba(245, 158, 11, 0.35);
}

.ok-alert-icon-txt {
  font-size: 44rpx;
  font-weight: 900;
  line-height: 1;
}

.ok-alert-icon--success .ok-alert-icon-txt {
  color: #059669;
}

.ok-alert-icon--warning .ok-alert-icon-txt {
  color: #d97706;
}

.ok-alert-body {
  position: relative;
  padding: 28rpx 40rpx 36rpx;
  text-align: center;
}

.ok-alert-icon-wrap + .ok-alert-body {
  padding-top: 20rpx;
}

.ok-alert-title {
  display: block;
  font-size: 36rpx;
  font-weight: 900;
  color: $ok-slate-800;
  line-height: 1.35;
}

.ok-alert-content {
  display: block;
  margin-top: 16rpx;
  font-size: 28rpx;
  color: $ok-slate-500;
  line-height: 1.55;
  white-space: pre-wrap;
}

.ok-alert-title:only-child,
.ok-alert-content:first-child {
  margin-top: 0;
}

.ok-alert-actions {
  display: flex;
  padding: 0 32rpx 36rpx;
}

.ok-alert-actions--single {
  padding-left: 40rpx;
  padding-right: 40rpx;
}

.ok-alert-actions .ok-alert-btn + .ok-alert-btn {
  margin-left: 20rpx;
}

.ok-alert-btn {
  flex: 1;
  height: 88rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
  font-weight: 700;
}

.ok-alert-btn--ghost {
  background: $ok-slate-100;
  color: $ok-slate-600;
}

.ok-alert-btn--primary {
  background: linear-gradient(135deg, $ok-forest-green, $ok-forest-green-dark);
  color: #fff;
  box-shadow: 0 10rpx 24rpx rgba(8, 66, 50, 0.26);
}

.ok-alert-btn--danger {
  background: linear-gradient(135deg, #ef4444, #b91c1c);
  color: #fff;
  box-shadow: 0 10rpx 24rpx rgba(185, 28, 28, 0.22);
}

.ok-alert-btn--hover {
  opacity: 0.88;
}
</style>
