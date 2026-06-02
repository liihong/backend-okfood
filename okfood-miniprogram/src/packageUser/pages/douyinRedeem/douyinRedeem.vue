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

        <view v-if="needDeliveryDate" class="card">
          <text class="label">起送日期（可选）</text>
          <picker mode="date" :value="deliveryDate" :start="minDeliveryDate" @change="onDateChange">
            <view class="date-pick">{{ deliveryDate || '暂不选择（仅入账，完善配送后生效）' }}</view>
          </picker>
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
import { getNavbarLayout } from '@/utils/navbar.js'
import { getMemberToken, clearMemberSession } from '@/utils/api.js'
import { redeemDouyinCertificate } from '@/utils/douyinApi.js'
import { markMinePageNeedsRefresh } from '@/utils/minePageRefresh.js'

const scrollStyle = ref({})
const code = ref('')
const deliveryDate = ref('')
const minDeliveryDate = ref('')
const submitting = ref(false)
/** 周卡/月卡映射时可选手选起送日；MVP 默认展示可选 */
const needDeliveryDate = ref(true)

function tomorrowShanghaiIso() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function onDateChange(e) {
  deliveryDate.value = e?.detail?.value || ''
}

async function onSubmit() {
  const c = (code.value || '').trim()
  if (c.length < 4) {
    uni.showToast({ title: '请输入有效券码', icon: 'none' })
    return
  }
  if (submitting.value) return
  submitting.value = true
  try {
    const body = { code: c }
    if (deliveryDate.value) body.delivery_start_date = deliveryDate.value
    const data = await redeemDouyinCertificate(body)
    markMinePageNeedsRefresh()
    uni.showModal({
      title: '兑换成功',
      content: data?.message || '兑换成功',
      showCancel: false,
      success: () => {
        if (data?.grant_type === 'coupon_template') {
          uni.navigateTo({ url: '/packageUser/pages/myCoupons/myCoupons' })
        } else {
          uni.navigateTo({ url: '/packageUser/pages/membershipCardList/membershipCardList' })
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
  const layout = getNavbarLayout()
  scrollStyle.value = { height: layout.scrollHeightPx }
  minDeliveryDate.value = tomorrowShanghaiIso()
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
.date-pick {
  padding: 20rpx;
  background: #f1f5f9;
  border-radius: 12rpx;
  font-size: 28rpx;
  color: #334155;
}
.submit-btn {
  margin-top: 8rpx;
  background: #0e5a44;
  color: #fff;
  border-radius: 999rpx;
  font-size: 30rpx;
}
.submit-btn[disabled] {
  opacity: 0.6;
}
</style>
