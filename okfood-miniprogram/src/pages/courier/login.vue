<template>
  <view class="page">
    <view class="page-header" :style="headerStyle">
      <text class="back-link" @click="onBack">返回</text>
    </view>

    <view v-if="resumeChecking" class="page-body page-body--center">
      <text class="resume-hint">正在恢复登录…</text>
    </view>

    <view v-else class="page-body">
      <view class="hero">
        <text class="rider-icon">🛵</text>
        <text class="rider-title">骑手端登录</text>
        <text class="rider-sub">请输入后台登记的配送员手机号</text>
      </view>

      <view class="form-card">
        <input
          v-model="phone"
          class="rider-input"
          type="number"
          maxlength="11"
          placeholder="输入 11 位手机号"
          placeholder-class="rider-input-ph"
        />
        <button class="btn-verify" :disabled="verifying" @click="verify">
          {{ verifying ? '验证中…' : '立即验证' }}
        </button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getNavbarLayout } from '@/utils/navbar.js'
import {
  getCourierPhone,
  getCourierToken,
  clearCourierToken,
  setCourierPhone,
  setAppUserMode,
  setCourierMeCache,
} from '@/utils/api.js'
import { courierLoginPhone, setCourierToken, fetchCourierMe } from '@/utils/courierApi.js'

const phone = ref('')
const verifying = ref(false)
const resumeChecking = ref(false)
const headerStyle = ref({ paddingTop: '20px' })

function syncHeaderInset() {
  const { statusBarHeight } = getNavbarLayout()
  headerStyle.value = {
    paddingTop: `${statusBarHeight + 6}px`,
  }
}

function onBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
  } else {
    setAppUserMode('member')
    uni.switchTab({ url: '/pages/order/index' })
  }
}

onShow(() => {
  syncHeaderInset()
  const stored = getCourierPhone()
  if (stored) phone.value = stored

  if (!getCourierToken()) {
    resumeChecking.value = false
    return
  }
  resumeChecking.value = true
  void (async () => {
    try {
      const me = await fetchCourierMe()
      setAppUserMode('courier')
      setCourierMeCache(me)
      uni.reLaunch({ url: '/pages/courier/home' })
    } catch (e) {
      const status = e && typeof e === 'object' ? e.status : undefined
      if (status === 401) clearCourierToken()
    } finally {
      resumeChecking.value = false
    }
  })()
})

async function verify() {
  const d = String(phone.value).replace(/\D/g, '')
  if (d.length !== 11) {
    uni.showToast({ title: '请输入 11 位手机号', icon: 'none' })
    return
  }
  if (verifying.value) return
  verifying.value = true
  try {
    const data = await courierLoginPhone(d)
    const token = data?.access_token
    if (!token) {
      uni.showToast({ title: '登录失败', icon: 'none' })
      return
    }
    setCourierToken(token)
    setCourierPhone(d)
    setAppUserMode('courier')
    try {
      const me = await fetchCourierMe()
      setCourierMeCache(me)
    } catch {
      /* 配送页 onShow 会再拉 /me */
    }
    uni.reLaunch({ url: '/pages/courier/home' })
  } catch (e) {
    const msg = e instanceof Error ? e.message : '验证失败'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    verifying.value = false
  }
}
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  box-sizing: border-box;
  background: linear-gradient(180deg, $ok-slate-50 0%, #ffffff 42%);
}

.page-header {
  padding-left: 32rpx;
  padding-right: 32rpx;
  padding-bottom: 8rpx;
}

.back-link {
  font-size: 28rpx;
  font-weight: 700;
  color: $ok-forest-green;
  padding: 12rpx 8rpx 12rpx 0;
  align-self: flex-start;
}

.page-body {
  padding: 24rpx 48rpx 48rpx;
  padding-bottom: calc(48rpx + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.page-body--center {
  align-items: center;
  justify-content: center;
  min-height: 40vh;
}

.resume-hint {
  font-size: 28rpx;
  font-weight: 700;
  color: $ok-slate-500;
}

.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-bottom: 48rpx;
}

.rider-icon {
  font-size: 112rpx;
  line-height: 1.2;
  margin-bottom: 28rpx;
}

.rider-title {
  font-size: 44rpx;
  font-weight: 950;
  font-style: italic;
  color: $ok-slate-800;
  margin-bottom: 16rpx;
}

.rider-sub {
  font-size: 26rpx;
  color: $ok-slate-500;
  font-weight: 600;
  line-height: 1.45;
  max-width: 560rpx;
}

.form-card {
  width: 100%;
  box-sizing: border-box;
  background: #ffffff;
  border-radius: 28rpx;
  padding: 40rpx 36rpx;
  box-shadow: 0 16rpx 48rpx rgba(15, 23, 42, 0.06);
  border: 1rpx solid $ok-slate-100;
}

.rider-input {
  width: 100%;
  box-sizing: border-box;
  background: $ok-slate-50;
  border: 2rpx solid $ok-slate-100;
  /* 微信端 input 大 padding 易导致占位符/文字纵向裁剪，用固定高度 + 行高对齐单行 */
  height: 100rpx;
  line-height: 100rpx;
  padding: 0 32rpx;
  border-radius: 20rpx;
  font-size: 34rpx;
  font-weight: 700;
  color: $ok-slate-800;
  text-align: center;
  margin-bottom: 32rpx;
}

.rider-input-ph {
  color: $ok-slate-400;
  font-weight: 600;
  font-size: 34rpx;
  line-height: 100rpx;
}

.btn-verify {
  width: 100%;
  box-sizing: border-box;
  background: $ok-sunshine-yellow;
  color: $ok-forest-green;
  padding: 32rpx;
  border-radius: 999rpx;
  font-weight: 950;
  font-size: 32rpx;
  border: none;
  box-shadow: 0 20rpx 40rpx rgba(250, 204, 21, 0.22);
}

.btn-verify[disabled] {
  opacity: 0.6;
}
</style>
