<template>
  <view class="rider-redirect-stub" />
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { setAppUserMode } from '@/utils/api.js'

/** 旧路由 pages/rider/home：开发者工具缓存或历史会话仍可能请求此路径，跳转至正式页 */
onLoad(() => {
  setAppUserMode('courier')
  uni.reLaunch({ url: '/pages/courier/home' })
})
</script>

<style scoped>
/* 占位页需产出 wxss，否则开发者工具仍报 ENOENT */
.rider-redirect-stub {
  display: none;
}
</style>
