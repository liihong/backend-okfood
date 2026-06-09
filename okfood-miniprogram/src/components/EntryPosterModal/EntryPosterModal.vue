<template>
  <view v-if="visible" class="poster-mask" @tap="onClose">
    <view class="poster-wrap" @tap.stop>
      <view class="poster-panel">
        <scroll-view scroll-y class="poster-scroll" :show-scrollbar="false">
          <image
            class="poster-img"
            :src="imageUrl"
            mode="widthFix"
            show-menu-by-longpress
          />
        </scroll-view>
      </view>
      <view class="poster-close" @tap="onClose">
        <text class="poster-close__icon">×</text>
      </view>
    </view>
  </view>
</template>

<script setup>
const props = defineProps({
  visible: { type: Boolean, default: false },
  imageUrl: { type: String, default: '' },
})

const emit = defineEmits(['update:visible', 'close'])

function onClose() {
  emit('update:visible', false)
  emit('close')
}
</script>

<style lang="scss" scoped>
.poster-mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48rpx 32rpx;
  background: rgba(15, 23, 42, 0.62);
}

.poster-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 640rpx;
}

.poster-panel {
  width: 100%;
  max-height: 82vh;
  border-radius: 24rpx;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 24rpx 64rpx rgba(15, 23, 42, 0.24);
}

.poster-scroll {
  width: 100%;
  max-height: 82vh;
  box-sizing: border-box;
}

.poster-img {
  display: block;
  width: 100%;
  vertical-align: top;
}

.poster-close {
  margin-top: 56rpx;
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(220, 220, 220, 0.45);
  border: 2rpx solid rgba(255, 255, 255, 0.35);
}

.poster-close__icon {
  color: rgba(255, 255, 255, 0.92);
  font-size: 48rpx;
  line-height: 1;
  font-weight: 300;
  margin-top: -4rpx;
}
</style>
