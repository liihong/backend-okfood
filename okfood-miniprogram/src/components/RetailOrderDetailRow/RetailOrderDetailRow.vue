<template>
  <view :class="['retail-order-row', { 'retail-order-row--block': block }]">
    <text class="retail-order-row__label">{{ label }}</text>
    <view class="retail-order-row__right">
      <text :class="['retail-order-row__value', valueClass]">{{ value }}</text>
      <slot name="action" />
    </view>
  </view>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    required: true,
  },
  value: {
    type: String,
    default: '—',
  },
  /** 是否纵向排列（如地址多行展示） */
  block: {
    type: Boolean,
    default: false,
  },
  /** 附加在 value 上的样式类 */
  valueClass: {
    type: String,
    default: '',
  },
})
</script>

<style lang="scss" scoped>
.retail-order-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16rpx;
  padding: 12rpx 0;
  font-size: 28rpx;
}

.retail-order-row--block {
  flex-direction: column;
}

.retail-order-row__label {
  flex-shrink: 0;
  color: #64748b;
}

.retail-order-row__right {
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  gap: 16rpx;
  flex: 1;
  min-width: 0;
}

.retail-order-row--block .retail-order-row__right {
  width: 100%;
  justify-content: space-between;
}

.retail-order-row__value {
  color: #0f172a;
  text-align: right;
  flex: 1;
  min-width: 0;
  line-height: 1.45;
  word-break: break-all;
}

.retail-order-row--block .retail-order-row__value {
  text-align: left;
}
</style>
