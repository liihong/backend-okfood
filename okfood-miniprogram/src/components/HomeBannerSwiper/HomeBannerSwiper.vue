<template>
  <view v-if="banners.length" class="home-banner-swiper">
    <swiper
      class="home-banner-swiper__track"
      :style="trackStyle"
      circular
      autoplay
      :interval="4000"
      :duration="500"
      indicator-dots
      indicator-color="rgba(255,255,255,0.45)"
      indicator-active-color="#ffffff"
    >
      <swiper-item v-for="item in banners" :key="item.id" class="home-banner-swiper__item" @click="onTap(item)">
        <image class="home-banner-swiper__img" :src="item.image_url" mode="aspectFill" />
      </swiper-item>
    </swiper>
  </view>
</template>

<script setup>
import { computed } from 'vue'
import { navigateHomeBanner } from '@/utils/homeApi.js'

/** 与 tabPageLayout 一致：Tab 页可用高度（扣除底栏） */
function tabPageViewportHeightPx(win) {
  let h = Number(win.windowHeight) || 0
  const sh = Number(win.screenHeight) || 0
  if (!h) return 667
  // #ifdef MP-WEIXIN
  if (sh > 0 && h >= sh - 12) {
    h = Math.max(120, h - 52)
  }
  // #endif
  return h
}

const trackStyle = computed(() => {
  const win = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
  const h = tabPageViewportHeightPx(win)
  return { height: `${Math.round(h * 0.5)}px` }
})

const props = defineProps({
  banners: { type: Array, default: () => [] },
  todayYmd: { type: String, default: '' },
})

function onTap(item) {
  navigateHomeBanner(item, props.todayYmd)
}
</script>

<style lang="scss" scoped>
.home-banner-swiper {
  width: 100%;
  margin-bottom: 24rpx;
}

.home-banner-swiper__track {
  width: 100%;
  overflow: hidden;
  background: transparent;
}

.home-banner-swiper__item {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.home-banner-swiper__img {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
