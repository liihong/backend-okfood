<template>
  <view class="page">
    <OkNavbar show-back title="抖音验券" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="wrap">
        <view class="guide card">
          <text class="guide-title">如何获取券码</text>
          <text class="guide-line">1. 打开抖音 App → 我 → 订单</text>
          <text class="guide-line">2. 找到已购买的团购券，复制券码</text>
          <text class="guide-line">3. 回到本页粘贴券码并提交兑换</text>
        </view>

        <view class="card">
          <text class="label">抖音券码</text>
          <textarea
            v-model="code"
            class="code-input"
            placeholder="请粘贴抖音订单中的券码"
            maxlength="128"
            :disabled="submitting"
          />
        </view>

        <button class="submit-btn" :loading="submitting" :disabled="submitting" @click="onSubmit">
          立即兑换
        </button>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getPageScrollStyle } from '@/utils/navbar.js'
import { getMemberToken, clearMemberSession } from '@/utils/api.js'
import { redeemDouyinCertificate } from '@/utils/douyinApi.js'
import { markMinePageNeedsRefresh } from '@/utils/minePageRefresh.js'
import { showOkAlert } from '@/utils/okAlert.js'

const scrollStyle = ref({})
const code = ref('')
const submitting = ref(false)

async function onSubmit() {
  const c = (code.value || '').trim()
  if (c.length < 4) {
    uni.showToast({ title: '请输入有效券码', icon: 'none' })
    return
  }
  if (submitting.value) return
  submitting.value = true
  try {
    const data = await redeemDouyinCertificate({ code: c })
    markMinePageNeedsRefresh()
    showOkAlert({
      title: '兑换成功',
      content: data?.message || '兑换成功',
      showCancel: false,
      tone: 'success',
      success: (r) => {
        if (!r.confirm) return
        if (data?.grant_type === 'coupon_template') {
          uni.navigateTo({ url: '/packageUser/pages/myCoupons/myCoupons' })
        } else {
          uni.switchTab({ url: '/pages/mine/index' })
        }
      },
    })
    code.value = ''
  } catch (e) {
    uni.showToast({ title: e instanceof Error ? e.message : '兑换失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

onShow(() => {
  scrollStyle.value = getPageScrollStyle()
  if (!getMemberToken()) {
    clearMemberSession()
    uni.reLaunch({ url: '/pages/mine/index' })
  }
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f8fafc;
}
.wrap {
  padding: 24rpx 28rpx 48rpx;
}
.card {
  background: #fff;
  border-radius: 20rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
}
.guide-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #0f172a;
  display: block;
  margin-bottom: 16rpx;
}
.guide-line {
  display: block;
  font-size: 26rpx;
  color: #64748b;
  line-height: 1.7;
}
.label {
  font-size: 28rpx;
  color: #334155;
  display: block;
  margin-bottom: 16rpx;
}
.code-input {
  width: 100%;
  min-height: 160rpx;
  padding: 20rpx;
  box-sizing: border-box;
  background: #f1f5f9;
  border-radius: 12rpx;
  font-size: 28rpx;
}
.submit-btn {
  margin-top: 8rpx;
  background: #73B054;
  color: #fff;
  border-radius: 999rpx;
  font-size: 30rpx;
}
.submit-btn[disabled] {
  opacity: 0.6;
}
</style>
