<template>
  <view v-if="visible" class="member-login-bar">
    <text class="member-login-bar__text">登录后享受完整会员服务</text>
    <button
      class="member-login-bar__btn"
      hover-class="member-login-bar__btn--hover"
      open-type="getPhoneNumber"
      @getphonenumber="onWxGetPhoneNumber"
    >
      立即登录
    </button>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getMemberToken } from '@/utils/api.js'
import {
  hasWxPhoneAuthDetail,
  wxMiniMemberLoginAndStore,
} from '@/utils/wxMemberLogin.js'

const emit = defineEmits(['logged-in'])

const visible = ref(false)

function syncVisible() {
  visible.value = !getMemberToken()
}

async function onWxGetPhoneNumber(e) {
  const detail = e?.detail
  if (!hasWxPhoneAuthDetail(detail)) {
    if (detail?.errMsg && !String(detail.errMsg).includes('cancel')) {
      uni.showToast({ title: '需要授权手机号', icon: 'none' })
    }
    return
  }
  uni.showLoading({ title: '登录中', mask: true })
  try {
    await wxMiniMemberLoginAndStore(detail)
    visible.value = false
    emit('logged-in')
    uni.showToast({ title: '登录成功', icon: 'success' })
  } catch (err) {
    uni.showToast({
      title: err instanceof Error ? err.message : '登录失败',
      icon: 'none',
    })
  } finally {
    uni.hideLoading()
  }
}

onMounted(syncVisible)
onShow(syncVisible)
</script>

<style lang="scss" scoped>
.member-login-bar {
  margin: 0 32rpx 24rpx;
  min-height: 88rpx;
  padding: 16rpx 24rpx;
  box-sizing: border-box;
  border-radius: 999rpx;
  background: #F4F9F1;
  border: 1rpx solid #C8DEB8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.member-login-bar__text {
  flex: 1;
  min-width: 0;
  font-size: 26rpx;
  font-weight: 700;
  color: #456D32;
}

.member-login-bar__btn {
  flex-shrink: 0;
  margin: 0;
  padding: 0 28rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 999rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 24rpx;
  font-weight: 900;
  border: none;
}

.member-login-bar__btn::after {
  border: none;
}

.member-login-bar__btn--hover {
  opacity: 0.92;
}
</style>
