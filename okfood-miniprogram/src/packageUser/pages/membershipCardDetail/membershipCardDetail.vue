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
              <view class="hero-badge" @tap="openShareSheet">
                <text class="hero-badge-txt">推荐给好友</text>
              </view>
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

          <view v-if="availableCoupons.length" class="coupon-box">
            <text class="coupon-lab">优惠券</text>
            <picker
              mode="selector"
              :range="availableCoupons"
              range-key="template_name"
              @change="onCouponPick"
            >
              <view class="coupon-pick">
                <text class="coupon-pick-txt">
                  {{ selectedCoupon ? `减 ¥${selectedCoupon.discount_yuan}` : '选择优惠券' }}
                </text>
                <text class="coupon-pick-arr">›</text>
              </view>
            </picker>
            <text v-if="discountDisp" class="coupon-save">已优惠 ¥{{ discountDisp }}</text>
          </view>
          <view v-else-if="couponsLoading" class="coupon-hint">加载优惠券…</view>

          <view class="scroll-pad" />
        </template>
        <view v-else class="hint">卡包不存在或已下架</view>
      </view>
    </scroll-view>

    <view v-if="tpl && !loading" class="footer">
      <view class="foot-lab">
        <text class="foot-cap">TOTAL PRICE</text>
        <text v-if="discountDisp" class="foot-orig">¥{{ saleDisp }}</text>
        <text class="foot-price">¥{{ payableDisp }}</text>
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

    <!-- 分享方式选择 -->
    <view v-if="shareSheetVisible" class="share-mask" @tap="closeShareSheet">
      <view class="share-sheet" @tap.stop>
        <text class="share-sheet-title">推荐给好友</text>
        <button class="share-sheet-btn" open-type="share" @tap="closeShareSheet">
          分享给微信好友
        </button>
        <view class="share-sheet-btn share-sheet-btn--plain" @tap="onShareTimelineGuide">
          分享到朋友圈
        </view>
        <view class="share-sheet-cancel" @tap="closeShareSheet">取消</view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  request,
  getMemberToken,
  clearMemberSession,
  isUserMeNotFoundError,
} from '@/utils/api.js'
import { runMembershipTemplateWechatPay } from '@/utils/memberCardPay.js'
import { listAvailableMemberCoupons } from '@/utils/memberCouponApi.js'
import { shouldOpenMemberSetup } from '@/utils/memberProfile.js'
import { markMinePageNeedsRefresh } from '@/utils/minePageRefresh.js'

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
const availableCoupons = ref([])
const selectedCouponId = ref(null)
const couponsLoading = ref(false)
const shareSheetVisible = ref(false)

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

const originalPriceNum = computed(() => {
  const n = Number(saleDisp.value)
  return Number.isFinite(n) ? n : null
})

const selectedCoupon = computed(() => {
  const id = selectedCouponId.value
  if (id == null) return null
  return availableCoupons.value.find((c) => Number(c.id) === Number(id)) || null
})

const discountDisp = computed(() => {
  const c = selectedCoupon.value
  if (!c) return null
  const n = Number(c.discount_yuan)
  return Number.isFinite(n) ? n.toFixed(2) : null
})

const payableDisp = computed(() => {
  const orig = originalPriceNum.value
  if (orig == null) return saleDisp.value
  const disc = discountDisp.value != null ? Number(discountDisp.value) : 0
  const pay = Math.max(0.01, orig - disc)
  return pay.toFixed(2)
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

/** 构建分享标题、路径与封面图 */
function buildSharePayload() {
  const t = tpl.value
  const id = templateId.value
  const name = t?.name ? String(t.name).trim() : '自律膳食卡'
  const meals = t?.meals_grant != null ? String(t.meals_grant) : ''
  const price = saleDisp.value
  const title = meals
    ? `推荐你办理「${name}」— OK饭 ${meals} 次餐，优惠价 ¥${price}`
    : `推荐你办理「${name}」— OK饭自律膳食卡`
  const path = `/packageUser/pages/membershipCardDetail/membershipCardDetail?templateId=${encodeURIComponent(String(id))}`
  const imageUrl =
    t?.card_style_image_url != null ? String(t.card_style_image_url).trim() : ''
  return {
    title,
    path,
    query: `templateId=${encodeURIComponent(String(id))}`,
    imageUrl,
  }
}

function enableWechatShareMenus() {
  // #ifdef MP-WEIXIN
  if (typeof wx !== 'undefined' && typeof wx.showShareMenu === 'function') {
    wx.showShareMenu({
      withShareTicket: true,
      menus: ['shareAppMessage', 'shareTimeline'],
    })
  }
  // #endif
}

function openShareSheet() {
  if (!tpl.value) return
  shareSheetVisible.value = true
}

function closeShareSheet() {
  shareSheetVisible.value = false
}

/** 朋友圈无 open-type 按钮，引导用户使用右上角菜单分享 */
function onShareTimelineGuide() {
  closeShareSheet()
  enableWechatShareMenus()
  uni.showModal({
    title: '分享到朋友圈',
    content: '请点击右上角 ··· 菜单，选择「分享到朋友圈」',
    showCancel: false,
  })
}

onShareAppMessage(() => {
  const { title, path, imageUrl } = buildSharePayload()
  return {
    title,
    path,
    ...(imageUrl ? { imageUrl } : {}),
  }
})

onShareTimeline(() => {
  const { title, query, imageUrl } = buildSharePayload()
  return {
    title,
    query,
    ...(imageUrl ? { imageUrl } : {}),
  }
})

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
    await loadCoupons()
  } catch (e) {
    if (isUserMeNotFoundError(e)) clearMemberSession()
    tpl.value = null
    uni.showToast({ title: e instanceof Error ? e.message : '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function loadCoupons() {
  if (!templateId.value) return
  couponsLoading.value = true
  selectedCouponId.value = null
  try {
    const rows = await listAvailableMemberCoupons({
      biz_type: 'member_card',
      membership_template_id: templateId.value,
    })
    availableCoupons.value = Array.isArray(rows) ? rows : []
    if (availableCoupons.value.length) {
      selectedCouponId.value = availableCoupons.value[0].id
    }
  } catch {
    availableCoupons.value = []
  } finally {
    couponsLoading.value = false
  }
}

function onCouponPick(e) {
  const idx = Number(e?.detail?.value)
  const row = availableCoupons.value[idx]
  selectedCouponId.value = row ? row.id : null
}

async function onPay() {
  if (!agreed.value || paying.value || !tpl.value) return
  paying.value = true
  try {
    let preProfile = null
    try {
      preProfile = await request('/api/user/me', { method: 'GET', retry: 0 })
    } catch {
      preProfile = null
    }
    const balBefore = Math.max(0, Math.floor(Number(preProfile?.balance) || 0))
    /** 仍有剩余餐次且履约信息已齐：视为有效期内续卡，仅叠加次数 */
    const activeRenewal =
      balBefore > 0 &&
      preProfile &&
      typeof preProfile === 'object' &&
      !shouldOpenMemberSetup(preProfile)

    const profileStartYmd =
      preProfile?.delivery_start_date != null
        ? String(preProfile.delivery_start_date).trim().slice(0, 10)
        : ''
    const payOut = await runMembershipTemplateWechatPay({
      membershipTemplateId: templateId.value,
      deliveryStartYmd: activeRenewal && profileStartYmd ? profileStartYmd : undefined,
      memberCouponId: selectedCouponId.value,
    })
    const paySynced = payOut?.paySynced !== false
    markMinePageNeedsRefresh()
    if (activeRenewal) {
      uni.showToast({
        title: paySynced ? '支付成功' : '支付已提交，状态同步中',
        icon: 'success',
      })
      setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
      return
    }
    if (paySynced) {
      uni.showToast({ title: '支付成功', icon: 'success' })
    } else {
      uni.showModal({
        title: '支付已提交',
        content:
          '微信已扣款，订单状态正在同步。请先完善配送信息；若后台长时间仍显示未缴，请联系客服核对。',
        showCancel: false,
      })
    }
    setTimeout(() => {
      uni.redirectTo({
        url: '/packageUser/pages/memberSetup/memberSetup?from=pay',
      })
    }, paySynced ? 400 : 80)
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
  enableWechatShareMenus()
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

.hero-badge:active {
  opacity: 0.88;
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

.foot-orig {
  font-size: 22rpx;
  color: $ok-slate-400;
  text-decoration: line-through;
  margin-right: 8rpx;
}

.coupon-box {
  margin-top: 16rpx;
  padding: 20rpx 24rpx;
  background: #fff;
  border-radius: 16rpx;
}

.coupon-lab {
  font-size: 26rpx;
  font-weight: 700;
  color: $ok-slate-800;
}

.coupon-pick {
  display: flex;
  justify-content: space-between;
  margin-top: 12rpx;
  padding: 16rpx 20rpx;
  background: $ok-slate-100;
  border-radius: 12rpx;
}

.coupon-save {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: $ok-emerald;
}

.coupon-hint {
  font-size: 24rpx;
  color: $ok-slate-500;
  padding: 8rpx 0;
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

.share-mask {
  position: fixed;
  inset: 0;
  z-index: 120;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-end;
}

.share-sheet {
  width: 100%;
  padding: 28rpx 32rpx calc(28rpx + env(safe-area-inset-bottom));
  background: #fff;
  border-radius: 28rpx 28rpx 0 0;
}

.share-sheet-title {
  display: block;
  text-align: center;
  font-size: 28rpx;
  font-weight: 700;
  color: $ok-slate-800;
  margin-bottom: 24rpx;
}

.share-sheet-btn {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  margin: 0 0 16rpx;
  padding: 0;
  border: none;
  border-radius: 20rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 30rpx;
  font-weight: 700;
}

.share-sheet-btn::after {
  border: none;
}

.share-sheet-btn--plain {
  display: flex;
  align-items: center;
  justify-content: center;
  background: $ok-slate-100;
  color: $ok-slate-800;
}

.share-sheet-cancel {
  margin-top: 8rpx;
  padding: 24rpx 0 8rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
}
</style>
