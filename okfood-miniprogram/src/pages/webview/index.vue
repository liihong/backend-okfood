<template>
  <view class="page" :style="pageStyle">
    <web-view v-if="webviewUrl" :src="webviewUrl" />
    <view v-else class="webview-empty">链接无效</view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

const webviewUrl = ref('')

onLoad((query) => {
  const raw = query?.url ? decodeURIComponent(String(query.url)) : ''
  webviewUrl.value = raw.startsWith('https://') ? raw : ''
})
</script>

<style scoped>
.webview-empty {
  padding: 80rpx 40rpx;
  text-align: center;
  color: #64748b;
}
</style>
