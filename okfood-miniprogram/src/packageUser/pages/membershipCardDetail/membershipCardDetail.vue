<template>
  <view class="page">
    <OkNavbar show-back title="购卡方案详情" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="wrap">
        <view v-if="loading" class="hint">加载中…</view>
        <template v-else-if="tpl">
          <view :class="['hero-card', heroCardClass]">
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
                <text class="hero-lab">{{ discountDisp ? '券后价' : '优惠价' }}</text>
                <text v-if="discountDisp" class="hero-orig-mini">¥{{ saleDisp }}</text>
                <text class="hero-yuan">¥{{ discountDisp ? payableDisp : saleDisp }}</text>
              </view>
            </view>
          </view>

          <view v-if="couponsLoading" class="coupon-section coupon-section--loading">
            <text class="coupon-section-hint">正在加载可用优惠券…</text>
          </view>
          <view v-else-if="availableCoupons.length" class="coupon-section">
            <view class="coupon-section-head">
              <text class="coupon-section-title">可用优惠券</text>
              <text v-if="discountDisp" class="coupon-section-save">已选 · 立减 ¥{{ discountDisp }}</text>
            </view>
            <view class="coupon-section-list">
              <view
                v-for="c in availableCoupons"
                :key="c.id"
                class="coupon-section-item"
              >
                <MemberCouponCard
                  :coupon="c"
                  :selected="Number(selectedCouponId) === Number(c.id)"
                  @select="onCouponSelect"
                />
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
import { onLoad, onShow, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getPageScrollStyle, FIXED_FOOTER_RESERVE_PX } from '@/utils/navbar.js'
import { showOkAlert } from '@/utils/okAlert.js'
import MemberCouponCard from '@/components/MemberCouponCard/MemberCouponCard.vue'
import {
  request,
  getMemberToken,
  clearMemberSession,
  isUserMeNotFoundError,
} from '@/utils/api.js'
import {
  promptGoPayPendingMemberCardOrder,
  runMembershipCardDetailPayWithPrompt,
} from '@/utils/membershipCardDetailPay.js'
import {
  listMemberCardOrders,
} from '@/utils/memberCardOrderApi.js'
import { listAvailableMemberCoupons, getMemberCouponReminder } from '@/utils/memberCouponApi.js'
import { filterMemberCardCouponsForTemplate, pickBestMemberCoupon } from '@/utils/memberCouponScope.js'

const DEFAULT_PRIV = [
  '全城顺丰免运费',
  '餐次自由随心停配',
  '持证营养师餐品搭配',
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
/** 避免 onLoad 与 loadOne 重复弹待支付提示 */
let pendingPayPrompted = false

function fetchPendingMemberCardOrderIdLocal() {
  return listMemberCardOrders({
    page: 1,
    page_size: 1,
    list_status: 'pending_pay',
  })
    .then(function (data) {
      const items = data && data.items
      const first = Array.isArray(items) ? items[0] : null
      const oid = first && first.id != null ? Number(first.id) : NaN
      return Number.isFinite(oid) && oid > 0 ? oid : null
    })
    .catch(function (_err) {
      void _err
      return null
    })
}

/** 进入购卡页：有待支付工单则弹窗引导 */
function maybePromptPendingPayOnEnter() {
  if (pendingPayPrompted) return Promise.resolve()
  pendingPayPrompted = true
  return fetchPendingMemberCardOrderIdLocal().then(function (orderId) {
    if (!orderId) return
    return promptGoPayPendingMemberCardOrder(orderId, selectedCouponId.value)
  })
}

const saleDisp = computed(() => {
  const t = tpl.value
  const s = t && t.sale_price_yuan
  const l = t && t.list_price_yuan
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
  const raw = tpl.value && tpl.value.purchase_notice
  if (raw && String(raw).trim()) {
    const lines = String(raw)
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (lines.length) return lines
  }
  return DEFAULT_PRIV
})

/** 周卡绿 / 月卡金 / 次卡蓝，与首页卡包、我的页方案卡配色一致 */
const heroCardClass = computed(() => {
  const t = tpl.value
  if (!t) return 'hero-card--week'
  const kl = String(t.kind_label || '').trim()
  const name = String(t.name || '').trim()
  if (kl.includes('月') || name.includes('月卡') || name.includes('月')) return 'hero-card--month'
  if (kl.includes('周') || name.includes('周卡') || name.includes('周')) return 'hero-card--week'
  if (kl.includes('次') || name.includes('次卡') || name.includes('次')) return 'hero-card--times'
  const mg = Number(t.meals_grant)
  if (Number.isFinite(mg) && mg >= 18) return 'hero-card--month'
  if (Number.isFinite(mg) && mg >= 6) return 'hero-card--week'
  return 'hero-card--times'
})

function toggleAgree() {
  agreed.value = !agreed.value
}

/** 构建分享标题、路径与封面图 */
function buildSharePayload() {
  const t = tpl.value
  const id = templateId.value
  const name = t && t.name ? String(t.name).trim() : '自律膳食卡'
  const meals = t && t.meals_grant != null ? String(t.meals_grant) : ''
  const price = saleDisp.value
  const title = meals
    ? `推荐你办理「${name}」— OK饭 ${meals} 次餐，优惠价 ¥${price}`
    : `推荐你办理「${name}」— OK饭自律膳食卡`
  const path = `/packageUser/pages/membershipCardDetail/membershipCardDetail?templateId=${encodeURIComponent(String(id))}`
  const imageUrl =
    t && t.card_style_image_url != null ? String(t.card_style_image_url).trim() : ''
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
  showOkAlert({
    title: '分享到朋友圈',
    content: '请点击右上角 ··· 菜单，选择「分享到朋友圈」',
    showCancel: false,
  })
}

onShareAppMessage(() => {
  const { title, path, imageUrl } = buildSharePayload()
  const payload = { title, path }
  if (imageUrl) payload.imageUrl = imageUrl
  return payload
})

onShareTimeline(() => {
  const { title, query, imageUrl } = buildSharePayload()
  const payload = { title, query }
  if (imageUrl) payload.imageUrl = imageUrl
  return payload
})

function loadOne() {
  if (!getMemberToken()) {
    loading.value = false
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(function () {
      uni.navigateBack()
    }, 400)
    return
  }
  const id = templateId.value
  if (!id) {
    loading.value = false
    return
  }
  loading.value = true
  request(`/api/user/membership-card-templates/${id}`, {
    method: 'GET',
    retry: 1,
  })
    .then(function (data) {
      tpl.value = data && typeof data === 'object' ? data : null
      return loadCoupons()
    })
    .catch(function (e) {
      if (isUserMeNotFoundError(e)) clearMemberSession()
      tpl.value = null
      uni.showToast({ title: e instanceof Error ? e.message : '加载失败', icon: 'none' })
    })
    .then(function () {
      loading.value = false
      if (tpl.value) {
        maybePromptPendingPayOnEnter().catch(function () {})
      }
    })
}

/** 结算页可用券；失败时用提醒接口兜底（避免线上未部署 available 时无券展示） */
function fetchCouponsForTemplate() {
  const tid = templateId.value
  return listAvailableMemberCoupons({
    biz_type: 'member_card',
    membership_template_id: tid,
  })
    .then(function (data) {
      return Array.isArray(data) ? data : []
    })
    .catch(function (_err) {
      void _err
      return []
    })
    .then(function (rows) {
      if (rows.length) return rows
      return getMemberCouponReminder()
        .then(function (reminder) {
          const coupons = reminder && reminder.coupons
          const all = Array.isArray(coupons) ? coupons : []
          return filterMemberCardCouponsForTemplate(all, tid)
        })
        .catch(function (_err2) {
          void _err2
          return []
        })
    })
}

function loadCoupons() {
  if (!templateId.value) return Promise.resolve()
  couponsLoading.value = true
  selectedCouponId.value = null
  return fetchCouponsForTemplate()
    .then(function (rows) {
      availableCoupons.value = rows
      const best = pickBestMemberCoupon(rows)
      if (best && best.id != null) selectedCouponId.value = best.id
    })
    .catch(function (_err) {
      void _err
      availableCoupons.value = []
    })
    .then(function () {
      couponsLoading.value = false
    })
}

function onCouponSelect(row) {
  if (!row || row.id == null) return
  selectedCouponId.value = row.id
}

function onPay() {
  if (!agreed.value || paying.value || !tpl.value) return
  paying.value = true
  runMembershipCardDetailPayWithPrompt({
    membershipTemplateId: templateId.value,
    memberCouponId: selectedCouponId.value,
  }).then(function () {
    paying.value = false
  }).catch(function () {
    paying.value = false
  })
}

/** scroll-view 在真机上须明确高度；calc(100vh) 在部分机型上无效，改用 windowHeight 像素值 */
function applyScrollLayout() {
  scrollStyle.value = getPageScrollStyle(FIXED_FOOTER_RESERVE_PX)
}

onShow(() => {
  applyScrollLayout()
})

onLoad((opts) => {
  const raw = opts && opts.templateId != null ? String(opts.templateId) : ''
  const id = parseInt(raw, 10)
  templateId.value = Number.isFinite(id) && id > 0 ? id : 0
  applyScrollLayout()
  enableWechatShareMenus()
  loadOne()
})
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
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
  margin-bottom: 28rpx;
}

.hero-card--week {
  background: linear-gradient(135deg, #73b054 0%, #365628 100%);
  box-shadow: 0 16rpx 40rpx rgba(15, 23, 42, 0.14);
}

.hero-card--month {
  background: linear-gradient(135deg, #b8860b 0%, #d97706 45%, #92400e 100%);
  box-shadow: 0 16rpx 40rpx rgba(146, 64, 14, 0.28);
}

.hero-card--times {
  background: linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 50%, #312e81 100%);
  box-shadow: 0 16rpx 40rpx rgba(30, 58, 95, 0.28);
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

.hero-orig-mini {
  display: block;
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.55);
  text-decoration: line-through;
  margin-bottom: 2rpx;
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

.coupon-section {
  margin-top: 20rpx;
}

.coupon-section--loading {
  padding: 16rpx 8rpx;
}

.coupon-section-hint {
  font-size: 24rpx;
  color: $ok-slate-500;
}

.coupon-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}

.coupon-section-title {
  font-size: 28rpx;
  font-weight: 800;
  color: $ok-slate-800;
}

.coupon-section-save {
  font-size: 24rpx;
  font-weight: 700;
  color: $ok-emerald;
}

.coupon-section-list {
  display: flex;
  flex-direction: column;
}

.coupon-section-list .coupon-section-item + .coupon-section-item {
  margin-top: 16rpx;
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
