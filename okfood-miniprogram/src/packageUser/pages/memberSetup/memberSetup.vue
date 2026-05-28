<template>
  <view class="page">
    <OkNavbar show-back :title="navbarTitle" />
    <scroll-view scroll-y class="scroll" :show-scrollbar="false">
      <view class="wrap">
        <text class="lead">{{ leadText }}</text>

        <view class="setup-module">
          <view class="section">
            <text class="sec-title">配送或门店自提</text>
            <radio-group class="pay-radio-group pay-radio-group--delivery" @change="onDeliveryModeChange">
              <label class="pay-radio-row">
                <radio value="delivery" :checked="deliveryMode === 'delivery'" :color="payRadioColor" />
                <text class="pay-radio-label">配送到家</text>
              </label>
              <label class="pay-radio-row">
                <radio value="pickup" :checked="deliveryMode === 'pickup'" :color="payRadioColor" />
                <text class="pay-radio-label">门店自提</text>
              </label>
            </radio-group>

            <!-- 配送：地址 -->
            <template v-if="deliveryMode === 'delivery'">
              <text class="sec-sub">顺丰同城配送，请指定默认收货地址（与「我的地址管理」同步）。</text>
              <view class="addr-box" @tap="goManageAddresses">
                <view class="addr-box-main">
                  <text :class="['addr-line', defaultAddressLine ? '' : 'addr-line--ph']">
                    {{ defaultAddressLine || '请添加并选择默认配送地址' }}
                  </text>
                  <text v-if="defaultAddressArea" class="addr-area">{{ defaultAddressArea }}</text>
                </view>
                <text class="addr-go">管理 ›</text>
              </view>
            </template>

            <!-- 自提：门店 + 确认 -->
            <template v-else-if="deliveryMode === 'pickup'">
              <text class="sec-title sec-title--inline">取餐门店</text>
              <view class="store-card">
                <text class="store-name">OK饭健康自律厨房</text>
                <text class="store-addr">{{ pickupStoreAddress }}</text>
              </view>
              <view class="ack-row" @tap="pickupAcknowledged = !pickupAcknowledged">
                <view :class="['ack-box', pickupAcknowledged ? 'ack-box--on' : '']">
                  <text v-if="pickupAcknowledged" class="ack-tick">✓</text>
                </view>
                <text class="ack-txt">我已确认到店自取位置与营业时间说明</text>
              </view>
            </template>

            <!-- 开始日期 -->
            <template v-if="deliveryMode === 'delivery' || deliveryMode === 'pickup'">
              <text class="sec-title sec-title--sp">{{
                deliveryMode === 'pickup' ? '开始自提日期' : '开始配送日期'
              }}</text>
              <text class="sec-sub">
                以上海业务日历为准；最早可选「今天」为起点。
              </text>
              <picker mode="date" :value="pickerDeliveryYmd" :start="minDeliveryYmd" @change="onDeliveryPick">
                <view class="date-picker-row">
                  <text :class="['date-picker-text', deliveryYmd ? '' : 'date-picker-text--ph']">
                    {{ deliveryYmd || '请选择业务日期' }}
                  </text>
                  <text class="date-picker-arrow">›</text>
                </view>
              </picker>
            </template>
          </view>

          <button
            class="submit-btn"
            :loading="submitting"
            @click="onSubmit"
          >
            {{ submitButtonText }}
          </button>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onShow, onLoad } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  request,
  getMemberToken,
  clearMemberSession,
  isUserMeNotFoundError,
} from '@/utils/api.js'
import {
  shouldOpenMemberSetup,
  shouldPromptMemberCardPay,
} from '@/utils/memberProfile.js'
import { minMemberDeliveryStartYmd } from '@/utils/menuApi.js'
import {
  normalizeAddressList,
  addressListRow,
  sortAddressesDefaultFirst,
  isAddressItemDefault,
} from '@/utils/addressApi.js'
import { requestRenewRemindSubscribeAndGrant } from '@/utils/renewSubscribeMsg.js'

/** 与 uni.scss $ok-forest-green 一致 */
const payRadioColor = '#0e5a44'

const pickupStoreAddress = '天安名邸小区门面房（OK饭健康餐门店）'
const deliveryMode = ref('delivery')
const deliveryYmd = ref('')
const minDeliveryYmd = ref(minMemberDeliveryStartYmd())
const submitting = ref(false)
const memberPhone = ref('')
const serverBalance = ref(0)

const resumeOnlyMode = ref(false)
/** 购卡/续卡支付成功跳转（from=pay）：须重新选择起始业务日，不因档案已有旧日期而自动退回「我的」 */
const postPaySetupMode = ref(false)
const resumeHintShown = ref(false)

const defaultAddressLine = ref('')
const defaultAddressArea = ref('')

const pickupAcknowledged = ref(false)

const pickerDeliveryYmd = computed(() => deliveryYmd.value || minDeliveryYmd.value)

const navbarTitle = computed(() => (resumeOnlyMode.value ? '恢复配送' : '完善配送信息'))

const submitButtonText = computed(() =>
  resumeOnlyMode.value ? '确认恢复配送' : '保存并返回「我的」',
)

const leadText = computed(() => {
  if (resumeOnlyMode.value) return '请选择恢复方式与开始的业务日期，提交后立即生效。'
  if (postPaySetupMode.value) {
    return '购卡或续卡已成功入账，请重新确认配送方式与收货信息，并选择新一周期的开始业务日期（续卡必须重选起始日），保存后将返回「我的」。'
  }
  return '请确认用餐履约方式：配送到家需默认收货地址；门店自提请确认取餐门店与首日。'
})

onLoad((options) => {
  const fr = options?.from != null ? String(options.from).trim() : ''
  resumeOnlyMode.value = fr === 'resume'
  postPaySetupMode.value = fr === 'pay'
  resumeHintShown.value = false
})

onShow(() => {
  minDeliveryYmd.value = minMemberDeliveryStartYmd()
  if (deliveryYmd.value && deliveryYmd.value < minDeliveryYmd.value) {
    deliveryYmd.value = ''
  }
  memberPhone.value = uni.getStorageSync('memberPhone') || ''
  if (!getMemberToken() || !memberPhone.value) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
    return
  }
  void loadProfile()
  void refreshDefaultAddress()
})

async function refreshDefaultAddress() {
  if (!getMemberToken()) {
    defaultAddressLine.value = ''
    defaultAddressArea.value = ''
    return
  }
  try {
    const data = await request('/api/user/me/addresses', { method: 'GET' })
    const sorted = sortAddressesDefaultFirst(normalizeAddressList(data))
    const defItem = sorted.find((item) => isAddressItemDefault(item))
    const row = defItem ? addressListRow(defItem, 0) : sorted.length ? addressListRow(sorted[0], 0) : null
    defaultAddressLine.value = row?.line?.trim() || ''
    defaultAddressArea.value = ''
  } catch {
    defaultAddressLine.value = ''
    defaultAddressArea.value = ''
  }
}

async function loadProfile() {
  const phone = memberPhone.value || uni.getStorageSync('memberPhone') || ''
  if (!phone) return
  try {
    const data = await request('/api/user/me', { method: 'GET' })
    minDeliveryYmd.value = minMemberDeliveryStartYmd()
    serverBalance.value = Math.max(0, Math.floor(Number(data.balance) || 0))

    if (shouldPromptMemberCardPay(data)) {
      uni.showToast({ title: '请先购买自律卡包', icon: 'none' })
      setTimeout(
        () =>
          uni.redirectTo({
            url: '/packageUser/pages/membershipCardList/membershipCardList',
          }),
        400,
      )
      return
    }

    const pausedWithBalance = data.delivery_deferred === true && serverBalance.value > 0

    if (resumeOnlyMode.value) {
      if (!pausedWithBalance) {
        uni.showToast({ title: '当前无需恢复配送', icon: 'none' })
        setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
        return
      }
    } else if (
      !postPaySetupMode.value &&
      !shouldOpenMemberSetup(data) &&
      !pausedWithBalance
    ) {
      uni.showToast({ title: '配送信息已完善', icon: 'success' })
      setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
      return
    }

    pickupAcknowledged.value = false

    if (data.delivery_deferred === true) {
      deliveryMode.value = data.store_pickup ? 'pickup' : 'delivery'
      deliveryYmd.value = ''
      if (
        resumeOnlyMode.value &&
        serverBalance.value > 0 &&
        !resumeHintShown.value
      ) {
        resumeHintShown.value = true
        setTimeout(() => {
          uni.showToast({
            title: '请选择配送方式与开始日期',
            icon: 'none',
            duration: 2400,
          })
        }, 400)
      }
    } else if (data.store_pickup === true) {
      deliveryMode.value = 'pickup'
      const ds = data.delivery_start_date != null ? String(data.delivery_start_date).trim() : ''
      let dPick = ds.length >= 10 ? ds.slice(0, 10) : ''
      if (dPick && dPick < minDeliveryYmd.value) dPick = ''
      deliveryYmd.value = dPick
    } else {
      deliveryMode.value = 'delivery'
      const ds = data.delivery_start_date != null ? String(data.delivery_start_date).trim() : ''
      let dPick = ds.length >= 10 ? ds.slice(0, 10) : ''
      if (dPick && dPick < minDeliveryYmd.value) dPick = ''
      deliveryYmd.value = dPick
    }

    if (postPaySetupMode.value && !resumeOnlyMode.value) {
      deliveryYmd.value = ''
      pickupAcknowledged.value = false
    }
  } catch (e) {
    if (isUserMeNotFoundError(e)) {
      clearMemberSession()
      uni.showToast({ title: '登录已失效，请重新登录', icon: 'none' })
      setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
      return
    }
    console.warn('loadProfile', e)
  }
}

function onDeliveryModeChange(e) {
  const v = e?.detail?.value
  if (v === 'pickup') {
    deliveryMode.value = 'pickup'
    pickupAcknowledged.value = false
  } else {
    deliveryMode.value = 'delivery'
  }
}

function onDeliveryPick(e) {
  const v = e.detail?.value || ''
  if (v && v < minDeliveryYmd.value) {
    uni.showToast({
      title: '该时段最早可选日期已更新，请重选',
      icon: 'none',
      duration: 2600,
    })
    return
  }
  deliveryYmd.value = v
}

function goManageAddresses() {
  uni.navigateTo({ url: '/packageUser/pages/address/list' })
}

async function onSubmit() {
  const phone = memberPhone.value || uni.getStorageSync('memberPhone') || ''
  if (!getMemberToken() || !phone) {
    uni.showToast({ title: '登录已失效', icon: 'none' })
    return
  }
  if (deliveryMode.value !== 'delivery' && deliveryMode.value !== 'pickup') {
    uni.showToast({ title: '请选择配送到家或门店自提', icon: 'none' })
    return
  }

  const d0 = deliveryYmd.value?.trim()
  if (!d0) {
    uni.showToast({
      title: deliveryMode.value === 'pickup' ? '请选择开始自提日期' : '请选择开始配送日期',
      icon: 'none',
    })
    return
  }
  if (d0 < minDeliveryYmd.value) {
    uni.showToast({
      title: '起始日须不早于当前允许的最小业务日（上海）',
      icon: 'none',
    })
    return
  }

  if (deliveryMode.value === 'delivery') {
    await refreshDefaultAddress()
    const line = String(defaultAddressLine.value || '').trim()
    if (!line) {
      uni.showToast({ title: '请先添加默认配送地址', icon: 'none' })
      return
    }
  } else if (!pickupAcknowledged.value) {
    uni.showToast({ title: '请确认已知晓门店自取位置', icon: 'none' })
    return
  }

  submitting.value = true
  try {
    await request('/api/user/profile', {
      method: 'PATCH',
      data: {
        delivery_deferred: false,
        delivery_start_date: d0,
        store_pickup: deliveryMode.value === 'pickup',
      },
    })
    await requestRenewRemindSubscribeAndGrant()
    uni.showToast({
      title: resumeOnlyMode.value ? '已恢复配送' : '已保存',
      icon: 'success',
      duration: 1800,
    })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/mine/index' })
    }, 380)
  } catch (err) {
    uni.showToast({ title: err?.message || '保存失败', icon: 'none', duration: 2800 })
  } finally {
    submitting.value = false
  }
}
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
  box-sizing: border-box;
}

.wrap {
  padding: 32rpx 40rpx calc(48rpx + env(safe-area-inset-bottom));
}

.lead {
  display: block;
  font-size: 28rpx;
  color: $ok-slate-600;
  font-weight: 700;
  line-height: 1.5;
  margin-bottom: 28rpx;
}

.notice {
  background: #fffbeb;
  border: 1rpx solid #fde68a;
  border-radius: 20rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 28rpx;
}

.notice--warn .notice-txt {
  color: #92400e;
}

.notice-txt {
  font-size: 26rpx;
  font-weight: 700;
  color: #92400e;
  line-height: 1.55;
}

.setup-module {
  padding: 28rpx 24rpx 32rpx;
  background: #fff;
  border-radius: 24rpx;
  border: 2rpx solid $ok-slate-100;
  box-sizing: border-box;
}

.section {
  margin-bottom: 8rpx;
}

.sec-title {
  display: block;
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-slate-800;
  margin-bottom: 20rpx;
}

.sec-title--inline {
  margin-top: 8rpx;
}

.sec-title--sp {
  margin-top: 28rpx;
}

.sec-sub {
  display: block;
  font-size: 22rpx;
  color: $ok-slate-500;
  font-weight: 700;
  margin: -8rpx 0 20rpx;
  line-height: 1.4;
}

.pay-radio-group {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 24rpx;
}

.pay-radio-row {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  background: #fff;
  border-radius: 999rpx;
  padding: 20rpx 24rpx;
  border: 3rpx solid $ok-slate-100;
  box-sizing: border-box;
  min-height: 88rpx;
}

.pay-radio-label {
  font-size: 28rpx;
  font-weight: 800;
  color: $ok-slate-800;
  flex-shrink: 0;
}

.pay-radio-group--delivery {
  margin-bottom: 20rpx;
  gap: 12rpx;
}

.pay-radio-group--delivery .pay-radio-row {
  padding: 18rpx 14rpx;
  gap: 10rpx;
}

.pay-radio-group--delivery .pay-radio-label {
  font-size: 24rpx;
}

.addr-box {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 20rpx;
  padding: 24rpx 28rpx;
  background: $ok-slate-50;
  border-radius: 20rpx;
  border: 2rpx solid $ok-slate-100;
  margin-bottom: 8rpx;
}

.addr-box-main {
  flex: 1;
  min-width: 0;
}

.addr-line {
  font-size: 28rpx;
  font-weight: 800;
  color: $ok-slate-800;
  line-height: 1.4;
}

.addr-line--ph {
  color: #94a3b8;
  font-weight: 700;
}

.addr-area {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  font-weight: 700;
  color: $ok-slate-500;
}

.addr-go {
  flex-shrink: 0;
  font-size: 28rpx;
  font-weight: 900;
  color: $ok-forest-green;
}

.store-card {
  padding: 24rpx 28rpx;
  background: linear-gradient(145deg, rgba(14, 90, 68, 0.08) 0%, #fff 100%);
  border-radius: 20rpx;
  border: 2rpx solid rgba(14, 90, 68, 0.18);
  margin-bottom: 20rpx;
}

.store-name {
  display: block;
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-forest-green;
  margin-bottom: 12rpx;
}

.store-addr {
  display: block;
  font-size: 26rpx;
  font-weight: 800;
  color: $ok-slate-700;
  line-height: 1.45;
}

.ack-row {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 16rpx;
  padding: 16rpx 0 8rpx;
}

.ack-box {
  width: 40rpx;
  height: 40rpx;
  border-radius: 10rpx;
  border: 3rpx solid $ok-slate-200;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2rpx;
}

.ack-box--on {
  background: $ok-forest-green;
  border-color: $ok-forest-green;
}

.ack-tick {
  font-size: 24rpx;
  font-weight: 900;
  color: #fff;
  line-height: 1;
}

.ack-txt {
  flex: 1;
  font-size: 26rpx;
  font-weight: 700;
  color: $ok-slate-700;
  line-height: 1.45;
}

.date-picker-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-radius: 999rpx;
  padding: 24rpx 36rpx;
  border: 3rpx solid $ok-slate-100;
  box-sizing: border-box;
  min-height: 88rpx;
}

.date-picker-text {
  font-size: 30rpx;
  font-weight: 800;
  color: #0f172a;
  flex: 1;
  min-width: 0;
}

.date-picker-text--ph {
  color: #64748b;
  font-weight: 700;
}

.date-picker-arrow {
  font-size: 36rpx;
  color: #cbd5e1;
  margin-left: 16rpx;
  flex-shrink: 0;
}

.submit-btn {
  margin-top: 36rpx;
  width: 100%;
  background: $ok-forest-green;
  color: #fff;
  font-size: 32rpx;
  font-weight: 950;
  border-radius: 999rpx;
  padding: 28rpx 0;
  border: none;
  line-height: 1.3;
}

.submit-btn::after {
  border: none;
}
</style>
