<template>
  <view class="ok-navbar" :style="wrapStyle">
    <view class="ok-navbar__inner" :style="innerStyle">
      <view class="ok-navbar__left">
        <text v-if="showBack" class="ok-navbar__back" @click="onBack">‹</text>
        <text v-if="showBrand" class="ok-navbar__brand">OK 饭 👌</text>
        <text
          v-if="showRiderEntry"
          class="ok-navbar__rider"
          @tap="goRiderLogin"
        >我是配送员</text>
        <text
          v-if="title"
          :class="['ok-navbar__title', showBack && !showBrand ? 'ok-navbar__title--sub' : '']"
        >
          {{ title }}
        </text>
      </view>
      <view class="ok-navbar__spacer" />
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { getNavbarLayout } from '@/utils/navbar.js'
import { getCourierToken, setAppUserMode } from '@/utils/api.js'

defineProps({
  /** Tab 首页左侧品牌 */
  showBrand: { type: Boolean, default: false },
  showBack: { type: Boolean, default: false },
  title: { type: String, default: '' },
  /** 菜单首页：配送员登录入口 */
  showRiderEntry: { type: Boolean, default: false },
})

/** 首帧即用系统值，避免默认 20/44 造成顶部多一大块留白 */
const lay0 = getNavbarLayout()
const statusBarHeight = ref(lay0.statusBarHeight)
const navContentHeight = ref(lay0.navContentHeight)

const wrapStyle = computed(() => ({
  paddingTop: `${statusBarHeight.value}px`,
}))

const innerStyle = computed(() => ({
  height: `${navContentHeight.value}px`,
}))

function onBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
  } else {
    uni.switchTab({ url: '/pages/order/index' })
  }
}

function goRiderLogin() {
  if (getCourierToken()) {
    setAppUserMode('courier')
    uni.reLaunch({ url: '/pages/courier/home' })
    return
  }
  uni.navigateTo({ url: '/pages/courier/login' })
}
</script>

<style lang="scss" scoped>
.ok-navbar {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: #ffffff;
  border-bottom: 0.5px solid #f1f5f9;
}

.ok-navbar__inner {
  display: flex;
  align-items: center;
  padding: 0 24rpx;
  box-sizing: border-box;
}

.ok-navbar__left {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex: 1;
  min-width: 0;
}

.ok-navbar__spacer {
  width: 180rpx;
  flex-shrink: 0;
}

.ok-navbar__back {
  font-size: 48rpx;
  font-weight: 950;
  color: $ok-forest-green;
  line-height: 1;
  padding-right: 8rpx;
}

.ok-navbar__brand {
  font-size: 34rpx;
  font-weight: 950;
  font-style: italic;
  color: $ok-forest-green;
  flex-shrink: 0;
}

.ok-navbar__rider {
  padding: 6rpx 14rpx;
  font-size: 22rpx;
  font-weight: 700;
  color: $ok-forest-green;
  border: 1rpx solid $ok-forest-green;
  border-radius: 999rpx;
  line-height: 1.3;
  flex-shrink: 0;
}

.ok-navbar__title {
  font-size: 34rpx;
  font-weight: 950;
  color: $ok-slate-800;
}

/* 子页（带返回）：与设计稿 addr-header 一致 */
.ok-navbar__title--sub {
  color: $ok-forest-green;
  font-style: italic;
  font-size: 44rpx;
}
</style>
