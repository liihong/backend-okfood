<template>
  <view
    v-if="rendered"
    class="poster-mask"
    :class="{ 'poster-mask--closing': closing }"
    @tap="onClose"
  >
    <view class="poster-wrap" :class="{ 'poster-wrap--closing': closing }" @tap.stop>
      <view class="poster-panel">
        <scroll-view scroll-y class="poster-scroll" :show-scrollbar="false">
          <image
            class="poster-img"
            :src="imageUrl"
            mode="widthFix"
            lazy-load
            show-menu-by-longpress
          />
        </scroll-view>
      </view>
      <view class="poster-close" :class="{ 'poster-close--closing': closing }" @tap="onClose">
        <text class="poster-close__icon">×</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  imageUrl: { type: String, default: '' },
})

const emit = defineEmits(['update:visible', 'close'])

/** 关闭动画时长（ms），需与 CSS 保持一致 */
const CLOSE_MS = 220

const rendered = ref(false)
const closing = ref(false)
let closeTimer = null

watch(
  () => props.visible,
  (v) => {
    if (closeTimer) {
      clearTimeout(closeTimer)
      closeTimer = null
    }
    if (v) {
      closing.value = false
      rendered.value = true
      return
    }
    if (!rendered.value) return
    closing.value = true
    closeTimer = setTimeout(() => {
      rendered.value = false
      closing.value = false
      closeTimer = null
    }, CLOSE_MS)
  },
  { immediate: true },
)

function onClose() {
  if (closing.value) return
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
  animation: poster-mask-in 0.3s ease forwards;
}

.poster-mask--closing {
  animation: poster-mask-out 0.22s ease forwards;
}

.poster-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 640rpx;
  animation: poster-panel-in 0.38s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

.poster-wrap--closing {
  animation: poster-panel-out 0.22s ease forwards;
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
  animation: poster-close-in 0.32s ease 0.14s both;
}

.poster-close--closing {
  animation: poster-close-out 0.18s ease forwards;
}

@keyframes poster-mask-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes poster-mask-out {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}

@keyframes poster-panel-in {
  from {
    opacity: 0;
    transform: scale(0.9) translateY(48rpx);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

@keyframes poster-panel-out {
  from {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
  to {
    opacity: 0;
    transform: scale(0.94) translateY(32rpx);
  }
}

@keyframes poster-close-in {
  from {
    opacity: 0;
    transform: scale(0.6);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes poster-close-out {
  from {
    opacity: 1;
    transform: scale(1);
  }
  to {
    opacity: 0;
    transform: scale(0.8);
  }
}

.poster-close__icon {
  color: rgba(255, 255, 255, 0.92);
  font-size: 48rpx;
  line-height: 1;
  font-weight: 300;
  margin-top: -4rpx;
}
</style>
