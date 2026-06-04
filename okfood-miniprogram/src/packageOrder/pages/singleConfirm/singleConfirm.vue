<template>
  <view class="page">
    <OkNavbar show-back title="确认订单" />
    <view v-if="loading" class="state">加载中…</view>
    <view v-else-if="loadError" class="state state--err">{{ loadError }}</view>
    <scroll-view v-else scroll-y class="scroll" :show-scrollbar="false" :style="scrollStyle">
      <view class="body">
        <view v-if="dish" class="card dish-card">
          <text class="card-label">餐品</text>
          <view class="dish-name-row">
            <text class="dish-name">{{ dish.name }}</text>
            <view class="dish-price-col">
              <text v-if="unitPrice != null" class="dish-price">¥ {{ unitPrice }} / 份</text>
              <text v-else class="dish-price dish-price--muted">待公布</text>
            </view>
          </view>
          <view class="dish-meta">
            <text class="meta-tag">{{ serviceDateDisplay }}</text>
          </view>
          <view v-if="dish.spiceLabel" class="dish-spice-line">
            <text class="dish-spice-line-txt">辣度 {{ dish.spiceLabel }}</text>
          </view>
          <view v-if="dish && dish.singleStockLimited" class="stock-row">
            <text>剩余可单点</text>
            <text class="stock-row-num">{{ dish.singleStockRemaining ?? 0 }}</text>
            <text> 份</text>
          </view>
          <view v-if="unitPrice != null" class="dish-total-row">
            <view class="dish-total-left">
              <text class="dish-total-label">小计</text>
              <view class="qty-inline" @catchtap="onStopTapBubble">
                <button type="button" class="qty-btn qty-btn--sm" @tap="decQty">−</button>
                <text class="qty-num qty-num--sm">{{ quantity }}</text>
                <button type="button" class="qty-btn qty-btn--sm" @tap="incQty">+</button>
              </view>
              <text class="dish-total-unit-hint">份</text>
            </view>
            <text class="dish-total-amt">¥ {{ payablePriceText }}</text>
            <text v-if="selectedCoupon" class="dish-total-orig">原价 ¥ {{ totalPriceText }}</text>
          </view>
        </view>

        <view v-if="availableCoupons.length && payMethod !== 'balance'" class="card coupon-card">
          <text class="card-label">优惠券</text>
          <picker
            mode="selector"
            :range="availableCoupons"
            range-key="template_name"
            @change="onCouponPick"
          >
            <view class="coupon-pick-row">
              <text>减 ¥{{ selectedCoupon ? selectedCoupon.discount_yuan : '0' }}</text>
              <text class="coupon-arr">›</text>
            </view>
          </picker>
        </view>
        <view v-else-if="couponsLoading" class="coupon-loading">加载优惠券…</view>

        <view class="card mode-card">
          <text class="card-label">取餐方式</text>
          <radio-group class="mode-group mode-group--row" @change="onFulfillModeChange">
            <label class="mode-row">
              <radio value="delivery" :checked="fulfillMode === 'delivery'" color="#0e5a44" />
              <text class="mode-label">配送到家</text>
            </label>
            <label class="mode-row">
              <radio value="pickup" :checked="fulfillMode === 'pickup'" color="#0e5a44" />
              <text class="mode-label">门店自提</text>
            </label>
          </radio-group>
        </view>

        <view v-if="showPaymentMethodCard" class="card pay-card">
          <text class="card-label">支付方式</text>
          <radio-group class="mode-group mode-group--row" @change="onPayMethodChange">
            <label class="mode-row">
              <radio value="wechat" :checked="payMethod === 'wechat'" color="#0e5a44" />
              <text class="mode-label">微信支付</text>
            </label>
            <label class="mode-row" @tap="onBalancePayLabelTap">
              <radio value="balance" :checked="payMethod === 'balance'" color="#0e5a44" />
              <text class="mode-label" :class="{ 'mode-label--muted': !balancePayEligible }">会员卡支付</text>
            </label>
          </radio-group>
          <view v-if="payMethod === 'balance'" class="pay-balance-hint">
            <text class="pay-balance-line">
              {{ balanceDisplay.plan_type || '会员卡' }} · 剩余
              <text class="pay-balance-num">{{ balanceDisplay.balance }}</text>
              <text v-if="balanceQuotaDenom">/{{ balanceQuotaDenom }}</text>
              次
            </text>
            <text v-if="balancePayInfo && balancePayInfo.reserve_for_today > 0" class="pay-balance-sub">
              今日套餐配送将预留 {{ balancePayInfo.reserve_for_today }} 次，本次将扣 {{ quantity }} 次
            </text>
            <text v-if="!balancePayEligible && balancePayHint" class="pay-balance-warn pay-balance-warn--inline">
              {{ balancePayHint }}
            </text>
          </view>
        </view>

        <view v-if="fulfillMode === 'delivery'" class="card addr-card">
          <view class="addr-head">
            <text class="card-label">配送地址</text>
            <text class="addr-manage" @tap="goAddressList">管理地址</text>
          </view>
          <view v-if="addressesLoading && !addressRows.length" class="addr-empty">
            <text>地址加载中…</text>
          </view>
          <view v-else-if="!addressRows.length" class="addr-empty">
            <text>暂无地址，请先添加</text>
            <button type="button" class="btn-ghost" hover-class="none" @tap="goAddressList">去添加</button>
          </view>
          <view v-else class="addr-list">
            <view
              v-for="(row, i) in addressRows"
              :key="row.id || i"
              class="addr-row"
              :class="{ 'addr-row--on': selectedIndex === i }"
              :data-index="i"
              @tap="onAddressRowTap"
            >
              <view class="addr-radio">
                <view v-if="selectedIndex === i" class="addr-dot-fill" />
                <view v-else class="addr-ring" />
              </view>
              <view class="addr-body">
                <view class="addr-line1">
                  <text class="addr-name">{{ row.name }}</text>
                  <text class="addr-phone">{{ row.phone }}</text>
                  <text v-if="row.isDefault" class="addr-badge">默认</text>
                </view>
                <text class="addr-line2">{{ row.line }}</text>
              </view>
            </view>
          </view>
        </view>

        <view class="hint-box">
          <text class="hint-title">支付说明</text>
          <text class="hint-text">
            <template v-if="payMethod === 'balance'">
              将使用会员卡剩余次数支付，无需微信支付。支付成功后{{ fulfillMode === 'delivery' ? '将按配送片区派单' : '为待取货状态，请按供餐日到店取餐' }}。
            </template>
            <template v-else-if="fulfillMode === 'delivery'">
              点击「去支付」将调起微信支付。支付成功后，系统会按配送片区派单给骑手。
            </template>
            <template v-else>
              门店自提：支付成功后为待取货状态，请按供餐日到店取餐；取走后由门店确认完成（无需骑手配送）。
            </template>
          </text>
        </view>
      </view>
    </scroll-view>

    <!-- 底栏固定在 scroll-view 外，避免真机上滚动区域吞掉「去支付」点击 -->
    <view v-if="!loading && !loadError && dish" class="pay-footer">
      <button
        class="btn-pay"
        hover-class="none"
        :class="{ 'btn-pay--disabled': !canPay || paying }"
        @tap="onPayButtonTap"
      >
        {{ payButtonText }}
      </button>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { onLoad, onShow, onReady } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  fetchMenuDetail,
  formatMenuPrice,
  formatServiceDateYmdWithWeekday,
  invalidateWeeklyMenuCache,
  singleOrderBlockReason,
} from '@/utils/menuApi.js'
import {
  getPageScrollStyle,
  schedulePageScrollLayout,
  FIXED_FOOTER_RESERVE_PX,
} from '@/utils/navbar.js'
import { getMemberToken, request } from '@/utils/api.js'
import {
  normalizeAddressList,
  sortAddressesDefaultFirst,
  getAddressRecordId,
  addressListRow,
} from '@/utils/addressApi.js'
import {
  createSingleMealOrder,
  fetchSingleMealBalancePayEligibility,
  paySingleMealOrderMemberBalance,
} from '@/utils/singleOrderApi.js'
import { paySingleMealOrderWechat } from '@/utils/singleOrderPay.js'
import { clearSingleOrderPayIntent, setSingleOrderPayIntent } from '@/utils/singleOrderPayIntent.js'
import { promptUnpaidOrderConflict } from '@/utils/unpaidOrderPrompt.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'
import { listAvailableMemberCoupons } from '@/utils/memberCouponApi.js'
import { showOkAlert } from '@/utils/okAlert.js'

const dish = ref(null)
const loading = ref(true)
const loadError = ref('')
const serviceDateYmd = ref('')

const serviceDateDisplay = computed(() => {
  const text = formatServiceDateYmdWithWeekday(serviceDateYmd.value)
  return text || '—'
})
const dishIdStr = ref('')
const addressRows = ref([])
const rawAddresses = ref([])
const selectedIndex = ref(0)
const paying = ref(false)
const scrollStyle = ref(getPageScrollStyle())
/** delivery | pickup */
const fulfillMode = ref('delivery')
const quantity = ref(1)
const QTY_MAX = 50
const availableCoupons = ref([])
const selectedCouponId = ref(null)
const couponsLoading = ref(false)
/** wechat | balance */
const payMethod = ref('wechat')
const balancePayInfo = ref(null)
const balancePayLoading = ref(false)
const addressesLoading = ref(false)
/** GET /api/user/me：用于展示周卡/月卡与剩余次数（不依赖资格接口是否上线） */
const memberProfile = ref(null)

const BALANCE_PLAN_TYPES = new Set(['周卡', '月卡'])

function inferPlanTypeFromQuota(me) {
  if (!me || typeof me !== 'object') return ''
  const quota = Math.floor(Number(me.meal_quota_total) || 0)
  const bal = Math.floor(Number(me.balance) || 0)
  if (bal <= 0 && quota <= 0) return ''
  if (quota >= 24) return '月卡'
  if (quota >= 6) return '周卡'
  return ''
}

function resolveMemberPlanType() {
  const fromElig = balancePayInfo.value?.plan_type
  const fromMe = memberProfile.value?.plan_type
  const raw = fromElig != null && String(fromElig).trim() ? fromElig : fromMe
  if (raw != null && String(raw).trim()) return String(raw).trim()
  return inferPlanTypeFromQuota(memberProfile.value)
}

const qtyMaxEffective = computed(() => {
  if (!dish.value) return 1
  if (!dish.value.singleStockLimited) return QTY_MAX
  const r = dish.value.singleStockRemaining
  if (r == null || !Number.isFinite(Number(r))) return 0
  return Math.max(0, Math.min(QTY_MAX, Math.floor(Number(r))))
})

/** 门店固定配送费（元），来自 menu/detail.base_delivery_fee_yuan */
const baseDeliveryFee = computed(() => {
  if (!dish.value) return 0
  const fee = formatMenuPrice(dish.value.baseDeliveryFee)
  return fee != null && fee >= 0 ? fee : 0
})

/** 当前取餐方式下的单价：配送=price；自提=price-配送费 */
const unitPrice = computed(() => {
  if (!dish.value) return null
  const list = formatMenuPrice(dish.value.price)
  if (list == null) return null
  if (fulfillMode.value === 'pickup') {
    return Math.max(0.01, list - baseDeliveryFee.value)
  }
  return list
})

const totalPriceText = computed(() => {
  const u = unitPrice.value
  if (u == null) return '—'
  const t = Number(u) * Math.max(1, Math.min(qtyMaxEffective.value, quantity.value))
  return Number.isFinite(t) ? t.toFixed(2) : '—'
})

const selectedCoupon = computed(() => {
  const id = selectedCouponId.value
  if (id == null) return null
  return availableCoupons.value.find((c) => Number(c.id) === Number(id)) || null
})

const payablePriceText = computed(() => {
  const orig = Number(totalPriceText.value)
  if (!Number.isFinite(orig)) return totalPriceText.value
  const disc = selectedCoupon.value ? Number(selectedCoupon.value.discount_yuan) : 0
  const d = Number.isFinite(disc) ? disc : 0
  return Math.max(0.01, orig - d).toFixed(2)
})

const showPaymentMethodCard = computed(() => BALANCE_PLAN_TYPES.has(resolveMemberPlanType()))

const balanceDisplay = computed(() => {
  const info = balancePayInfo.value
  const me = memberProfile.value
  const plan = resolveMemberPlanType()
  return {
    plan_type: plan || null,
    balance: Math.max(
      0,
      Math.floor(Number(info?.balance ?? me?.balance) || 0),
    ),
    meal_quota_total: Math.max(
      0,
      Math.floor(Number(info?.meal_quota_total ?? me?.meal_quota_total) || 0),
    ),
  }
})

const balancePayEligible = computed(() => !!balancePayInfo.value?.can_use)

const balancePayHint = computed(() => {
  const msg = balancePayInfo.value?.message
  return msg && String(msg).trim() ? String(msg).trim() : '当前无法使用次数支付，请使用微信支付'
})

const balanceQuotaDenom = computed(() => {
  const t = balanceDisplay.value.meal_quota_total
  return t > 0 ? t : null
})

const payButtonText = computed(() => {
  if (paying.value) return '处理中…'
  if (payMethod.value === 'balance') return '使用次数支付'
  return '去支付'
})

/** 不可支付时的原因（空串表示可支付）；用于底栏点击提示，避免 disabled 静默无反应 */
const payBlockReason = computed(() => {
  if (paying.value) return ''
  if (!dish.value) return '餐品加载中，请稍候'
  const stockMsg = singleOrderBlockReason(dish.value, serviceDateYmd.value)
  if (stockMsg) return stockMsg
  if (unitPrice.value == null) return '单点价格待公布'
  const q = Math.max(1, Math.min(qtyMaxEffective.value, quantity.value))
  if (q < 1) return '请选择购买份数'
  if (payMethod.value === 'balance' && !balancePayEligible.value) {
    return balancePayHint.value || '当前无法使用次数支付'
  }
  if (fulfillMode.value === 'delivery') {
    if (!addressRows.value.length) return '请先添加配送地址'
    const item = rawAddresses.value[selectedIndex.value]
    if (!getAddressRecordId(item)) return '请选择有效配送地址'
  }
  return ''
})

const canPay = computed(() => !payBlockReason.value)

/** 微信小程序对 async 的 @tap 偶发不触发；用具名同步入口再调 handlePay */
function onPayButtonTap() {
  const reason = payBlockReason.value
  if (reason) {
    uni.showToast({ title: reason, icon: 'none', duration: 2800 })
    return
  }
  if (paying.value || !dish.value) return
  void handlePay()
}

function onFulfillModeChange(e) {
  const v = e?.detail?.value
  fulfillMode.value = v === 'pickup' ? 'pickup' : 'delivery'
}

function onPayMethodChange(e) {
  const v = e?.detail?.value === 'balance' ? 'balance' : 'wechat'
  applyPayMethod(v)
}

/** 微信小程序不支持 @tap="a = b"；须用具名方法 */
function applyPayMethod(v) {
  if (v === 'balance' && !balancePayEligible.value) {
    uni.showToast({ title: balancePayHint.value, icon: 'none', duration: 2800 })
    payMethod.value = 'wechat'
    return
  }
  payMethod.value = v
  if (v === 'balance') {
    selectedCouponId.value = null
  }
}

function onBalancePayLabelTap() {
  if (!balancePayEligible.value) {
    uni.showToast({ title: balancePayHint.value, icon: 'none', duration: 2800 })
  }
}

function onStopTapBubble() {
  /* 阻止数量区点击冒泡；勿用 @tap.stop 无处理器（基础库会报 method "false"） */
}

function onAddressRowTap(e) {
  const idx = Number(e?.currentTarget?.dataset?.index)
  if (Number.isFinite(idx) && idx >= 0) {
    selectedIndex.value = idx
  }
}

function applyAddressList(raw) {
  const list = sortAddressesDefaultFirst(normalizeAddressList(raw))
  rawAddresses.value = list
  addressRows.value = list.map((it, i) => addressListRow(it, i))
  if (selectedIndex.value >= addressRows.value.length) {
    selectedIndex.value = 0
  }
}

function buildFallbackBalancePayInfo(err) {
  const plan = resolveMemberPlanType()
  if (!BALANCE_PLAN_TYPES.has(plan)) return null
  const me = memberProfile.value
  const msg =
    err instanceof Error && (err.status === 404 || /404|不存在/.test(err.message))
      ? '次数支付服务未就绪，请使用微信支付或联系门店'
      : '暂时无法校验次数，请使用微信支付'
  return {
    can_use: false,
    message: msg,
    balance: Math.max(0, Math.floor(Number(me?.balance) || 0)),
    meal_quota_total: Math.max(0, Math.floor(Number(me?.meal_quota_total) || 0)),
    plan_type: plan,
    reserve_for_today: 0,
    required_balance: 0,
  }
}

async function refreshBalancePayEligibility() {
  if (!dish.value || !getMemberToken()) {
    balancePayInfo.value = null
    return
  }
  if (!showPaymentMethodCard.value) {
    balancePayInfo.value = null
    payMethod.value = 'wechat'
    return
  }
  const q = Math.max(1, Math.min(qtyMaxEffective.value, quantity.value))
  balancePayLoading.value = true
  try {
    const data = await fetchSingleMealBalancePayEligibility(q)
    balancePayInfo.value = data && typeof data === 'object' ? data : null
    if (!balancePayInfo.value?.plan_type && resolveMemberPlanType()) {
      balancePayInfo.value = {
        ...balancePayInfo.value,
        plan_type: resolveMemberPlanType(),
        balance: balanceDisplay.value.balance,
        meal_quota_total: balanceDisplay.value.meal_quota_total,
      }
    }
    if (payMethod.value === 'balance' && !balancePayInfo.value?.can_use) {
      payMethod.value = 'wechat'
    }
  } catch (e) {
    balancePayInfo.value = buildFallbackBalancePayInfo(e)
    payMethod.value = 'wechat'
  } finally {
    balancePayLoading.value = false
  }
}

async function refreshMemberProfile() {
  if (!getMemberToken()) {
    memberProfile.value = null
    return
  }
  try {
    const me = await request('/api/user/me', { method: 'GET', retry: 1 })
    memberProfile.value = me && typeof me === 'object' ? me : null
  } catch (_meErr) {
    memberProfile.value = null
  }
}

function decQty() {
  if (quantity.value > 1) quantity.value -= 1
}

function incQty() {
  const cap = qtyMaxEffective.value
  if (quantity.value < cap) quantity.value += 1
}

async function loadCoupons() {
  const dishId = dish.value?.dishId
  if (!dishId) return
  couponsLoading.value = true
  selectedCouponId.value = null
  try {
    const q = Math.max(1, Math.min(qtyMaxEffective.value, quantity.value))
    const rows = await listAvailableMemberCoupons({
      biz_type: 'single_meal',
      dish_id: Number(dishId),
      quantity: q,
      store_pickup: fulfillMode.value === 'pickup',
    })
    availableCoupons.value = Array.isArray(rows) ? rows : []
    if (availableCoupons.value.length) {
      selectedCouponId.value = availableCoupons.value[0].id
    }
  } catch (_couponErr) {
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

watch(quantity, () => {
  if (dish.value) {
    void loadCoupons()
    void refreshBalancePayEligibility()
  }
})

watch(fulfillMode, () => {
  if (dish.value) void loadCoupons()
})

/** scroll-view 在真机上须明确高度；v-else 延迟挂载时需 schedule 重算 */
function applyScrollLayout() {
  schedulePageScrollLayout((style) => {
    scrollStyle.value = style
  }, FIXED_FOOTER_RESERVE_PX)
}

onReady(() => {
  applyScrollLayout()
})

onLoad((options) => {
  applyScrollLayout()
  const raw =
    (options && options.dish_id) ||
    (options && options.dishId) ||
    (options && options.id) ||
    ''
  dishIdStr.value = raw ? decodeURIComponent(String(raw)) : ''
  const svcRaw =
    (options && options.service_date) ||
    (options && options.serviceDate) ||
    (options && options.date) ||
    ''
  serviceDateYmd.value = svcRaw ? decodeURIComponent(String(svcRaw)).trim() : ''

  if (!getMemberToken()) {
    loading.value = false
    loadError.value = '请先登录'
    showOkAlert({
      title: '需要登录',
      content: '请先在「我的」中完成手机号登录后再下单。',
      confirmText: '去登录',
      success: (r) => {
        if (r.confirm) uni.switchTab({ url: '/pages/mine/index' })
        else uni.navigateBack()
      },
    })
    return
  }

  if (!dishIdStr.value) {
    loading.value = false
    loadError.value = '缺少餐品参数'
    return
  }
  if (!serviceDateYmd.value) {
    loading.value = false
    loadError.value = '缺少供餐日期'
    return
  }
  const block = singleOrderBlockReason(null, serviceDateYmd.value)
  if (block) {
    loading.value = false
    loadError.value = block
    return
  }
  loadPage()
})

onShow(() => {
  applyScrollLayout()
  if (!dishIdStr.value || !getMemberToken()) return
  void refreshMemberProfile().then(() => {
    if (dish.value) void refreshBalancePayEligibility()
  })
  refreshAddressesOnly()
})

async function refreshAddressesOnly() {
  addressesLoading.value = true
  try {
    const raw = await request('/api/user/me/addresses', { method: 'GET', retry: 1 })
    applyAddressList(raw)
  } catch (_addrErr) {
    /* 保留已有列表 */
  } finally {
    addressesLoading.value = false
  }
}

async function loadPage() {
  loading.value = true
  loadError.value = ''
  dish.value = null
  try {
    const [d, raw] = await Promise.all([
      fetchMenuDetail(dishIdStr.value, serviceDateYmd.value),
      request('/api/user/me/addresses', { method: 'GET', retry: 1 }),
    ])
    try {
      const me = await request('/api/user/me', { method: 'GET', retry: 1 })
      memberProfile.value = me && typeof me === 'object' ? me : null
    } catch (_meErr) {
      memberProfile.value = null
    }
    if (!d) throw new Error('暂无餐品数据')
    dish.value = d
    const stockBlock = singleOrderBlockReason(d, serviceDateYmd.value)
    if (stockBlock) {
      loadError.value = stockBlock
    }
    const cap = d.singleStockLimited
      ? Math.max(0, Math.min(QTY_MAX, d.singleStockRemaining != null ? Math.floor(Number(d.singleStockRemaining)) : 0))
      : QTY_MAX
    if (quantity.value > cap) {
      quantity.value = Math.max(1, cap)
    }
    if (quantity.value < 1) {
      quantity.value = 1
    }
    applyAddressList(raw)
    selectedIndex.value = 0
    if (formatMenuPrice(dish.value.price) == null) {
      loadError.value = '该餐品单点价格待公布'
    } else {
      await Promise.all([loadCoupons(), refreshBalancePayEligibility()])
    }
  } catch (e) {
    const msg =
      e instanceof Error
        ? e.message
        : typeof e === 'string'
          ? e
          : '加载失败'
    loadError.value = msg || '加载失败'
  } finally {
    loading.value = false
    nextTick(() => applyScrollLayout())
  }
}

function goAddressList() {
  uni.navigateTo({
    url: '/packageUser/pages/address/list',
    fail: () => {
      uni.showToast({ title: '无法打开地址页', icon: 'none' })
    },
  })
}

async function handlePay() {
  const block = payBlockReason.value
  if (block) {
    uni.showToast({ title: block, icon: 'none', duration: 2800 })
    return
  }
  if (paying.value || !dish.value) return
  const isPickup = fulfillMode.value === 'pickup'
  let addressId = null
  if (!isPickup) {
    const item = rawAddresses.value[selectedIndex.value]
    addressId = getAddressRecordId(item)
    if (!addressId) {
      uni.showToast({ title: '请选择有效配送地址', icon: 'none' })
      return
    }
  }
  const p = formatMenuPrice(dish.value.price)
  if (p == null) {
    uni.showToast({ title: '单点价格待公布', icon: 'none' })
    return
  }
  const q = Math.max(1, Math.min(qtyMaxEffective.value, quantity.value))

  paying.value = true
  uni.showLoading({ title: '创建订单…', mask: true })
  try {
    await syncWxMiniOpenidFromLogin()
    const payload = {
      dish_id: Number(dish.value.dishId),
      delivery_date: serviceDateYmd.value,
      store_pickup: isPickup,
      quantity: q,
    }
    if (!isPickup) {
      payload.member_address_id = Number(addressId)
    }
    if (payMethod.value !== 'balance' && selectedCouponId.value != null) {
      payload.member_coupon_id = Math.floor(Number(selectedCouponId.value))
    }
    const out = await createSingleMealOrder(payload)
    const orderId = out && typeof out === 'object' ? out.id : null
    if (orderId == null) {
      throw new Error('订单创建响应异常')
    }
    setSingleOrderPayIntent(orderId, payMethod.value === 'balance' ? 'balance' : 'wechat')
    if (payMethod.value === 'balance') {
      uni.showLoading({ title: '扣次支付…', mask: true })
      await paySingleMealOrderMemberBalance(orderId)
    } else {
      uni.showLoading({ title: '拉起支付…', mask: true })
      const payResult = await paySingleMealOrderWechat(orderId)
      if (!payResult.paySynced) {
        uni.showToast({ title: '支付成功，订单同步中请稍后刷新', icon: 'none', duration: 3000 })
      }
    }
    clearSingleOrderPayIntent(orderId)
    showOkAlert({
      title: '支付成功',
      content: '您的餐品后厨已开始备餐',
      tone: 'success',
      showCancel: false,
      success: () => {
        try {
          uni.setStorageSync('okfood_open_my_orders_after_checkout', '1')
        } catch (_storageErr) {
          /* ignore */
        }
        invalidateWeeklyMenuCache()
        uni.switchTab({ url: '/pages/mine/index' })
      },
    })
  } catch (e) {
    const raw = e && typeof e === 'object' ? e : {}
    const errMsg = typeof raw.errMsg === 'string' ? raw.errMsg : ''
    if (errMsg.includes('cancel') || errMsg.includes('取消')) {
      uni.showToast({ title: '已取消支付', icon: 'none' })
    } else if (promptUnpaidOrderConflict(e, { kind: 'single' })) {
      /* 已引导至待支付订单 */
    } else {
      const msg = e instanceof Error ? e.message : errMsg || '下单或支付失败'
      uni.showToast({ title: msg, icon: 'none' })
    }
  } finally {
    paying.value = false
    uni.hideLoading()
  }
}
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  box-sizing: border-box;
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
}

.state {
  flex: 1;
  min-height: 50vh;
  padding: 48rpx 40rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
  box-sizing: border-box;
}

.state--err {
  color: $ok-urgent-red;
}

.body {
  padding: 24rpx 40rpx 32rpx;
}

.pay-footer {
  flex-shrink: 0;
  padding: 16rpx 40rpx;
  padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
  background: #fff;
  box-shadow: 0 -8rpx 24rpx rgba(15, 23, 42, 0.06);
  box-sizing: border-box;
}

.card {
  background: #fcfaf2;
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 28rpx;
}

.card-label {
  display: block;
  font-size: 22rpx;
  font-weight: 900;
  color: $ok-slate-400;
  margin-bottom: 16rpx;
}

.dish-name-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24rpx;
}

.dish-name {
  flex: 1;
  min-width: 0;
  font-size: 36rpx;
  font-weight: 950;
  color: $ok-slate-800;
  line-height: 1.35;
}

.dish-price-col {
  flex-shrink: 0;
  max-width: 46%;
  text-align: right;
}

.stock-row {
  margin-top: 20rpx;
  font-size: 26rpx;
  color: $ok-slate-600;
  font-weight: 800;
}
.stock-row-num {
  color: $ok-forest-green;
  font-size: 32rpx;
  font-weight: 950;
  margin: 0 4rpx;
}

.dish-meta {
  margin-top: 16rpx;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16rpx;
}

.meta-tag {
  font-size: 22rpx;
  color: $ok-forest-green;
  font-weight: 800;
  background: rgba(14, 90, 68, 0.12);
  padding: 8rpx 20rpx;
  border-radius: 16rpx;
}

.dish-spice-line {
  margin-top: 12rpx;
}

.dish-spice-line-txt {
  font-size: 24rpx;
  font-weight: 850;
  color: #9a3412;
}

.dish-price {
  font-size: 34rpx;
  font-weight: 1000;
  color: $ok-forest-green;
  line-height: 1.35;
}

.dish-price--muted {
  font-size: 26rpx;
  color: $ok-slate-400;
  font-weight: 800;
}

.dish-total-row {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 2rpx dashed rgba(14, 90, 68, 0.2);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  flex-wrap: wrap;
}

.dish-total-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12rpx 16rpx;
  min-width: 0;
  flex: 1;
}

.dish-total-label {
  font-size: 26rpx;
  font-weight: 800;
  color: $ok-slate-600;
  flex-shrink: 0;
}

.dish-total-unit-hint {
  font-size: 26rpx;
  font-weight: 800;
  color: $ok-slate-500;
  flex-shrink: 0;
}

.dish-total-amt {
  font-size: 36rpx;
  font-weight: 1000;
  color: $ok-forest-green;
  flex-shrink: 0;
}

.qty-inline {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.mode-group {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.mode-group--row {
  flex-direction: row;
  align-items: stretch;
  gap: 20rpx;
}

.mode-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  padding: 20rpx 12rpx;
  background: #fff;
  border-radius: 20rpx;
  border: 2rpx solid $ok-slate-100;
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
}

.mode-label {
  font-size: 28rpx;
  font-weight: 800;
  color: $ok-slate-800;
}

.mode-label--muted {
  color: $ok-slate-400;
}

.pay-balance-hint {
  margin-top: 20rpx;
  padding: 20rpx 24rpx;
  background: rgba(14, 90, 68, 0.08);
  border-radius: 20rpx;
}

.pay-balance-line {
  display: block;
  font-size: 26rpx;
  font-weight: 850;
  color: $ok-slate-700;
  line-height: 1.5;
}

.pay-balance-num {
  color: $ok-forest-green;
  font-weight: 1000;
  font-size: 32rpx;
}

.pay-balance-sub {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  font-weight: 750;
  color: $ok-slate-500;
  line-height: 1.45;
}

.pay-balance-warn--inline {
  display: block;
  margin-top: 12rpx;
  font-size: 24rpx;
  font-weight: 800;
  color: #b45309;
  line-height: 1.45;
}

.qty-btn {
  width: 72rpx;
  height: 72rpx;
  line-height: 72rpx;
  padding: 0;
  margin: 0;
  background: #fff;
  border: 3rpx solid $ok-forest-green;
  border-radius: 16rpx;
  font-size: 40rpx;
  font-weight: 900;
  color: $ok-forest-green;
}

.qty-btn--sm {
  width: 56rpx;
  height: 56rpx;
  line-height: 56rpx;
  font-size: 32rpx;
  border-radius: 14rpx;
  border-width: 2rpx;
}

.qty-btn::after {
  border: none;
}

.qty-num {
  min-width: 48rpx;
  text-align: center;
  font-size: 36rpx;
  font-weight: 950;
  color: $ok-slate-800;
}

.qty-num--sm {
  min-width: 40rpx;
  font-size: 30rpx;
}
.addr-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8rpx;
}

.addr-manage {
  font-size: 24rpx;
  font-weight: 800;
  color: $ok-forest-green;
}

.addr-empty {
  padding: 24rpx 0;
  text-align: center;
  font-size: 26rpx;
  color: $ok-slate-500;
}

.btn-ghost {
  margin-top: 20rpx;
  background: transparent;
  color: $ok-forest-green;
  font-size: 28rpx;
  font-weight: 800;
  border: 2rpx solid $ok-forest-green;
  border-radius: 24rpx;
}

.addr-list {
  margin-top: 12rpx;
}

.addr-row {
  display: flex;
  gap: 20rpx;
  padding: 24rpx 16rpx;
  border-radius: 24rpx;
  border: 2rpx solid transparent;
  margin-bottom: 12rpx;
  background: #fff;
}

.addr-row--on {
  border-color: $ok-forest-green;
  background: rgba(14, 90, 68, 0.06);
}

.addr-radio {
  width: 44rpx;
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 4rpx;
}

.addr-dot-fill {
  width: 28rpx;
  height: 28rpx;
  border-radius: 50%;
  background: $ok-forest-green;
  margin-top: 4rpx;
  flex-shrink: 0;
}

.addr-ring {
  width: 28rpx;
  height: 28rpx;
  border: 2rpx solid $ok-slate-200;
  border-radius: 50%;
  margin-top: 4rpx;
}

.addr-body {
  flex: 1;
  min-width: 0;
}

.addr-line1 {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.addr-name {
  font-size: 30rpx;
  font-weight: 900;
  color: $ok-slate-800;
}

.addr-phone {
  font-size: 26rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.addr-badge {
  font-size: 20rpx;
  color: $ok-forest-green;
  font-weight: 800;
  border: 1rpx solid rgba(14, 90, 68, 0.35);
  padding: 4rpx 12rpx;
  border-radius: 12rpx;
}

.addr-line2 {
  font-size: 26rpx;
  color: $ok-slate-500;
  line-height: 1.5;
  font-weight: 600;
}

.hint-box {
  padding: 8rpx 0 32rpx;
}

.hint-title {
  display: block;
  font-size: 24rpx;
  font-weight: 900;
  color: $ok-slate-600;
  margin-bottom: 12rpx;
}

.hint-text {
  font-size: 24rpx;
  color: $ok-slate-400;
  line-height: 1.65;
  font-weight: 600;
}

.btn-pay {
  width: 100%;
  padding: 24rpx 32rpx;
  background: $ok-forest-green;
  color: #fff;
  border: none;
  border-radius: 40rpx;
  font-size: 28rpx;
  font-weight: 900;
  line-height: 1.35;
  margin-top: 16rpx;
  box-shadow: 0 16rpx 32rpx rgba(14, 90, 68, 0.18);
}

.btn-pay::after {
  border: none;
}

.btn-pay--disabled {
  opacity: 0.45;
  box-shadow: none;
}
</style>
