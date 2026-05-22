<template>
  <view class="redirect-page" />
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'

/** 兼容旧链接：统一跳转到 Tab「订单」页 */
onLoad(() => {
  uni.switchTab({ url: '/pages/orders/index' })
})
</script>

<style lang="scss" scoped>
.redirect-page {
  min-height: 100vh;
  background: $ok-slate-50;
}
</style>
