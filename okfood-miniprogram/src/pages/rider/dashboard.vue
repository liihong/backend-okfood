<template>
  <view class="rider-redirect-stub" />
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { setAppUserMode } from '@/utils/api.js'

/** 旧路由 pages/rider/dashboard：同上 */
onLoad(() => {
  setAppUserMode('courier')
  uni.reLaunch({ url: '/pages/courier/home' })
})
</script>

<style scoped>
.rider-redirect-stub {
  display: none;
}
</style>
