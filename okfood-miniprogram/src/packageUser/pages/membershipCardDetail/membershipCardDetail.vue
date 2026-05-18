<template>
  <view class="page">
    <OkNavbar show-back title="购卡方案详情" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="wrap">
        <view v-if="loading" class="hint">加载中…</view>
        <template v-else-if="tpl">
          <view class="hero-card">
            <view class="hero-water">OK</view>
            <view class="hero-top">
              <view>
                <text class="hero-cap">OK FITNESS VIP SPECIAL</text>
                <text class="hero-name">{{ tpl.name }}</text>
              </view>
              <view class="hero-badge"><text class="hero-badge-txt">推荐办理</text></view>
            </view>
            <view class="hero-foot">
              <view>
                <text class="hero-lab">含餐数</text>
                <text class="hero-num">{{ tpl.meals_grant }} 次</text>
              </view>
              <view class="hero-foot-r">
                <text class="hero-lab">优惠价</text>
                <text class="hero-yuan">¥{{ saleDisp }}</text>
              </view>
            </view>
          </view>

          <view class="section">
            <text class="sec-title">方案核心优势</text>
            <view class="sec-box">
              <text class="sec-p">{{ introText }}</text>
            </view>
          </view>

          <view class="section">
            <text class="sec-title">核心特权权益</text>
            <view v-for="(line, i) in privilegeLines" :key="i" class="priv-row">
              <text class="priv-ico">✓</text>
              <text class="priv-txt">{{ line }}</text>
            </view>
          </view>

          <view class="agree" @tap="toggleAgree">
            <view :class="['agree-box', agreed ? 'agree-box--on' : '']">
              <text v-if="agreed" class="agree-tick">✓</text>
            </view>
            <text class="agree-txt">阅读并同意《OK饭自律膳食卡用户服务及配送协议》</text>
          </view>
          <view class="scroll-pad" />
        </template>
        <view v-else class="hint">卡包不存在或已下架</view>
      </view>
    </scroll-view>

    <view v-if="tpl && !loading" class="footer">
      <view class="foot-lab">
        <text class="foot-cap">TOTAL PRICE</text>
        <text class="foot-price">¥{{ saleDisp }}</text>
      </view>
      <button
        class="foot-pay"
        :loading="paying"
        :disabled="!agreed || paying"
        @tap="onPay"
      >
        💳 立即支付开卡
      </button>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  request,
  getMemberToken,
  clearMemberSession,
  isUserMeNotFoundError,
} from '@/utils/api.js'
import { runMembershipTemplateWechatPay } from '@/utils/memberCardPay.js'

const DEFAULT_PRIV = [
  '全城顺丰免运费',
  '餐次自由随心停配',
  '专属营养餐单建议',
]

const scrollStyle = ref({})
const loading = ref(true)
const paying = ref(false)
const agreed = ref(true)
const tpl = ref(null)
const templateId = ref(0)

const pan4 = computed(() => {
  const id = templateId.value || 0
  return String(id).padStart(4, '0').slice(-4)
})

const saleDisp = computed(() => {
  const s = tpl.value?.sale_price_yuan
  const l = tpl.value?.list_price_yuan
  if (s != null && s !== '') return String(s)
  if (l != null && l !== '') return String(l)
  return '—'
})

const introText = computed(() => {
  const t = tpl.value
  if (!t) return ''
  return (
    (t.intro_short && String(t.intro_short).trim()) ||
    `含 ${t.meals_grant} 次自律健康餐，购买后餐次将入账至您的账户，稍候请完善配送信息即可开始用餐。`
  )
})

const privilegeLines = computed(() => {
  const raw = tpl.value?.purchase_notice
  if (raw && String(raw).trim()) {
    const lines = String(raw)
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (lines.length) return lines
  }
  return DEFAULT_PRIV
})

function toggleAgree() {
  agreed.value = !agreed.value
}

async function loadOne() {
  if (!getMemberToken()) {
    loading.value = false
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 400)
    return
  }
  const id = templateId.value
  if (!id) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const data = await request(`/api/user/membership-card-templates/${id}`, {
      method: 'GET',
      retry: 1,
    })
    tpl.value = data && typeof data === 'object' ? data : null
  } catch (e) {
    if (isUserMeNotFoundError(e)) clearMemberSession()
    tpl.value = null
    uni.showToast({ title: e instanceof Error ? e.message : '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function onPay() {
  if (!agreed.value || paying.value || !tpl.value) return
  paying.value = true
  try {
    await runMembershipTemplateWechatPay({
      membershipTemplateId: templateId.value,
    })
    uni.showToast({ title: '支付成功', icon: 'success' })
    const q = `title=${encodeURIComponent('完善配送信息')}`
    setTimeout(() => {
      uni.redirectTo({
        url: `/packageUser/pages/address/address?${q}`,
      })
    }, 400)
  } catch (e) {
    const msg =
      e instanceof Error ? e.message : typeof e === 'string' ? e : '支付未完成'
    if (msg.includes('cancel') || msg.includes('取消')) {
      uni.showToast({ title: '已取消支付', icon: 'none' })
    } else {
      uni.showToast({ title: msg, icon: 'none', duration: 2800 })
    }
  } finally {
    paying.value = false
  }
}

onLoad((opts) => {
  const raw = opts?.templateId != null ? String(opts.templateId) : ''
  const id = parseInt(raw, 10)
  templateId.value = Number.isFinite(id) && id > 0 ? id : 0
  scrollStyle.value = { flex: '1', minHeight: '0' }
  void loadOne()
})
</script>

<style lang="scss" scoped>
.page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: $ok-slate-50;
  box-sizing: border-box;
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
}

.wrap {
  padding: 24rpx 32rpx 0;
}

.hint {
  padding: 48rpx 0;
  text-align: center;
  color: $ok-slate-500;
  font-size: 28rpx;
}

.hero-card {
  position: relative;
  border-radius: 28rpx;
  padding: 28rpx 28rpx 24rpx;
  overflow: hidden;
  background: linear-gradient(135deg, #0e5a44 0%, #052e24 100%);
  box-shadow: 0 16rpx 40rpx rgba(15, 23, 42, 0.14);
  margin-bottom: 28rpx;
}

.hero-water {
  position: absolute;
  right: -16rpx;
  bottom: -24rpx;
  font-size: 140rpx;
  font-weight: 900;
  color: rgba(255, 255, 255, 0.07);
  pointer-events: none;
}

.hero-top {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.hero-cap {
  display: block;
  font-size: 18rpx;
  letter-spacing: 0.12em;
  color: rgba(255, 255, 255, 0.65);
  margin-bottom: 10rpx;
}

.hero-name {
  display: block;
  font-size: 32rpx;
  font-weight: 800;
  color: #fff;
  line-height: 1.3;
  padding-right: 12rpx;
}

.hero-badge {
  flex-shrink: 0;
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: rgba(250, 204, 21, 0.95);
}

.hero-badge-txt {
  font-size: 22rpx;
  color: #422006;
  font-weight: 600;
}

.hero-pan {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 24rpx;
  font-size: 26rpx;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.92);
}

.hero-foot {
  position: relative;
  z-index: 1;
  margin-top: 28rpx;
  padding-top: 22rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}

.hero-lab {
  display: block;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.68);
  margin-bottom: 6rpx;
}

.hero-num {
  font-size: 34rpx;
  font-weight: 700;
  color: #fff;
}

.hero-foot-r {
  text-align: right;
}

.hero-yuan {
  font-size: 40rpx;
  font-weight: 800;
  color: #fef08a;
}

.section {
  margin-bottom: 28rpx;
}

.sec-title {
  display: block;
  font-size: 30rpx;
  font-weight: 800;
  color: $ok-slate-800;
  margin-bottom: 16rpx;
}

.sec-box {
  background: $ok-slate-100;
  border-radius: 20rpx;
  padding: 24rpx 24rpx;
}

.sec-p {
  font-size: 26rpx;
  color: $ok-slate-600;
  line-height: 1.55;
}

.priv-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  background: #fff;
  border-radius: 16rpx;
  padding: 20rpx 22rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 4rpx 16rpx rgba(15, 23, 42, 0.05);
}

.priv-ico {
  flex-shrink: 0;
  width: 36rpx;
  height: 36rpx;
  line-height: 36rpx;
  text-align: center;
  border-radius: 10rpx;
  background: rgba(16, 185, 129, 0.2);
  color: $ok-forest-green;
  font-size: 22rpx;
  font-weight: 700;
}

.priv-txt {
  flex: 1;
  font-size: 26rpx;
  color: $ok-slate-700;
  line-height: 1.45;
}

.agree {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 12rpx 0 8rpx;
}

.agree-box {
  width: 36rpx;
  height: 36rpx;
  border-radius: 8rpx;
  border: 2rpx solid $ok-slate-300;
  box-sizing: border-box;
  margin-top: 4rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.agree-box--on {
  background: $ok-emerald;
  border-color: $ok-emerald;
}

.agree-tick {
  color: #fff;
  font-size: 22rpx;
  font-weight: 800;
}

.agree-txt {
  flex: 1;
  font-size: 24rpx;
  color: $ok-slate-600;
  line-height: 1.45;
}

.scroll-pad {
  height: 180rpx;
}

.footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  padding: 20rpx 28rpx calc(20rpx + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.96);
  border-top: 0.5rpx solid $ok-slate-200;
  box-shadow: 0 -8rpx 24rpx rgba(15, 23, 42, 0.06);
}

.foot-cap {
  display: block;
  font-size: 20rpx;
  letter-spacing: 0.08em;
  color: $ok-slate-400;
  margin-bottom: 4rpx;
}

.foot-price {
  font-size: 40rpx;
  font-weight: 900;
  color: $ok-urgent-red;
}

.foot-pay {
  flex: 1;
  max-width: 420rpx;
  height: 88rpx;
  line-height: 88rpx;
  border-radius: 44rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 28rpx;
  font-weight: 700;
  border: none;
  margin: 0;
}

.foot-pay[disabled] {
  opacity: 0.45;
}
</style>
