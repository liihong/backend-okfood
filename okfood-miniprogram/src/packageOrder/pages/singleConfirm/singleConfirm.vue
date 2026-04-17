<template>
  <view class="page">
    <OkNavbar show-back title="确认订单" />
    <view v-if="loading" class="state">加载中…</view>
    <view v-else-if="loadError" class="state state--err">{{ loadError }}</view>
    <scroll-view v-else scroll-y class="scroll" :show-scrollbar="false" :style="scrollStyle">
      <view class="body">
        <view v-if="dish" class="card dish-card">
          <text class="card-label">餐品</text>
          <text class="dish-name">{{ dish.name }}</text>
          <view class="dish-meta">
            <text class="meta-tag">{{ dish.day }} · {{ serviceDateYmd }}</text>
            <text v-if="priceLabel != null" class="dish-price">¥ {{ priceLabel }}</text>
            <text v-else class="dish-price dish-price--muted">待公布</text>
          </view>
        </view>

        <view class="card addr-card">
          <view class="addr-head">
            <text class="card-label">配送地址</text>
            <text class="addr-manage" @tap="goAddressList">管理地址</text>
          </view>
          <view v-if="!addressRows.length" class="addr-empty">
            <text>暂无地址，请先添加</text>
            <button class="btn-ghost" @tap="goAddressList">去添加</button>
          </view>
          <view v-else class="addr-list">
            <view
              v-for="(row, i) in addressRows"
              :key="row.id || i"
              class="addr-row"
              :class="{ 'addr-row--on': selectedIndex === i }"
              @tap="selectedIndex = i"
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
            点击「去支付」将调起微信支付。支付成功后，系统会自动确认订单并按配送片区派单给对应骑手，您可在配送端查看进度。
          </text>
        </view>

        <button
          class="btn-pay"
          :disabled="!canPay || paying"
          :class="{ 'btn-pay--disabled': !canPay || paying }"
          @tap="handlePay"
        >
          {{ paying ? '处理中…' : '去支付' }}
        </button>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  fetchMenuDetail,
  formatMenuPrice,
  isSingleOrderServiceDate,
} from '@/utils/menuApi.js'
import { getNavbarLayout } from '@/utils/navbar.js'
import { getMemberToken, request } from '@/utils/api.js'
import {
  normalizeAddressList,
  sortAddressesDefaultFirst,
  getAddressRecordId,
  addressListRow,
} from '@/utils/addressApi.js'
import { createSingleMealOrder, fetchWechatJsapiPayParams } from '@/utils/singleOrderApi.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'

const dish = ref(null)
const loading = ref(true)
const loadError = ref('')
const serviceDateYmd = ref('')
const dishIdStr = ref('')
const addressRows = ref([])
const rawAddresses = ref([])
const selectedIndex = ref(0)
const paying = ref(false)
const scrollStyle = ref({ height: '400px' })

const priceLabel = computed(() => {
  if (!dish.value) return null
  return formatMenuPrice(dish.value.price)
})

const canPay = computed(() => {
  if (!dish.value || !serviceDateYmd.value) return false
  if (!isSingleOrderServiceDate(serviceDateYmd.value)) return false
  if (priceLabel.value == null) return false
  if (!addressRows.value.length) return false
  const row = addressRows.value[selectedIndex.value]
  return !!(row && row.id)
})

onLoad((options) => {
  try {
    const win = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
    const { navBarTotal } = getNavbarLayout()
    const h = Math.max(240, (win.windowHeight || 667) - navBarTotal)
    scrollStyle.value = { height: `${h}px` }
  } catch {
    /* ignore */
  }
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
    uni.showModal({
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
  if (!isSingleOrderServiceDate(serviceDateYmd.value)) {
    loading.value = false
    loadError.value = '仅当日与次日餐品可单点'
    return
  }

  loadPage()
})

onShow(() => {
  if (!dishIdStr.value || !getMemberToken()) return
  refreshAddressesOnly()
})

async function refreshAddressesOnly() {
  try {
    const raw = await request('/api/user/me/addresses', { method: 'GET', retry: 1 })
    const list = sortAddressesDefaultFirst(normalizeAddressList(raw))
    rawAddresses.value = list
    addressRows.value = list.map((it, i) => addressListRow(it, i))
    if (selectedIndex.value >= addressRows.value.length) {
      selectedIndex.value = 0
    }
  } catch {
    /* 保留列表；首次 loadPage 会报错 */
  }
}

async function loadPage() {
  loading.value = true
  loadError.value = ''
  dish.value = null
  try {
    const [d, raw] = await Promise.all([
      fetchMenuDetail(dishIdStr.value),
      request('/api/user/me/addresses', { method: 'GET', retry: 1 }),
    ])
    if (!d) throw new Error('暂无餐品数据')
    dish.value = d
    const list = sortAddressesDefaultFirst(normalizeAddressList(raw))
    rawAddresses.value = list
    addressRows.value = list.map((it, i) => addressListRow(it, i))
    selectedIndex.value = 0
    if (!list.length) {
      uni.showModal({
        title: '暂无配送地址',
        content: '请先添加配送地址，以便系统按位置划片并派单。',
        confirmText: '去添加',
        success: (r) => {
          if (r.confirm) uni.navigateTo({ url: '/packageUser/pages/address/list' })
        },
      })
    }
    if (formatMenuPrice(dish.value.price) == null) {
      loadError.value = '该餐品单点价格待公布'
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
  }
}

function goAddressList() {
  uni.navigateTo({ url: '/packageUser/pages/address/list' })
}

async function handlePay() {
  if (!canPay.value || paying.value || !dish.value) return
  const item = rawAddresses.value[selectedIndex.value]
  const addressId = getAddressRecordId(item)
  if (!addressId) {
    uni.showToast({ title: '地址无效', icon: 'none' })
    return
  }
  const p = formatMenuPrice(dish.value.price)
  if (p == null) {
    uni.showToast({ title: '单点价格待公布', icon: 'none' })
    return
  }

  paying.value = true
  uni.showLoading({ title: '创建订单…', mask: true })
  try {
    await syncWxMiniOpenidFromLogin()
    const out = await createSingleMealOrder({
      dish_id: Number(dish.value.dishId),
      member_address_id: Number(addressId),
      delivery_date: serviceDateYmd.value,
    })
    const orderId = out && typeof out === 'object' ? out.id : null
    if (orderId == null) {
      throw new Error('订单创建响应异常')
    }
    uni.showLoading({ title: '拉起支付…', mask: true })
    const pay = await fetchWechatJsapiPayParams(orderId)
    await new Promise((resolve, reject) => {
      uni.requestPayment({
        provider: 'wxpay',
        timeStamp: String(pay.timeStamp),
        nonceStr: pay.nonceStr,
        package: pay.package,
        signType: pay.signType || 'MD5',
        paySign: pay.paySign,
        success: resolve,
        fail: reject,
      })
    })
    const area = typeof out.routing_area === 'string' ? out.routing_area : '—'
    uni.showModal({
      title: '支付成功',
      content: `¥${p} · ${out.delivery_date || serviceDateYmd.value}\n片区：${area}\n订单已提交。微信支付回调确认后系统将完成派单，骑手可在配送端查看该单。`,
      showCancel: false,
      success: () => {
        uni.navigateBack()
      },
    })
  } catch (e) {
    const raw = e && typeof e === 'object' ? e : {}
    const errMsg = typeof raw.errMsg === 'string' ? raw.errMsg : ''
    if (errMsg.includes('cancel') || errMsg.includes('取消')) {
      uni.showToast({ title: '已取消支付', icon: 'none' })
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
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  box-sizing: border-box;
}

.scroll {
  flex: 1;
  width: 100%;
  box-sizing: border-box;
}

.state {
  flex: 1;
  padding: 48rpx 40rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.state--err {
  color: $ok-urgent-red;
}

.body {
  padding: 24rpx 40rpx 80rpx;
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

.dish-name {
  font-size: 36rpx;
  font-weight: 950;
  color: $ok-slate-800;
  line-height: 1.35;
}

.dish-meta {
  margin-top: 20rpx;
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

.dish-price {
  font-size: 40rpx;
  font-weight: 1000;
  color: $ok-forest-green;
}

.dish-price--muted {
  font-size: 28rpx;
  color: $ok-slate-400;
  font-weight: 800;
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
  padding: 44rpx;
  background: $ok-forest-green;
  color: #fff;
  border: none;
  border-radius: 48rpx;
  font-size: 34rpx;
  font-weight: 950;
  box-shadow: 0 30rpx 60rpx rgba(14, 90, 68, 0.2);
}

.btn-pay--disabled {
  opacity: 0.45;
  box-shadow: none;
}
</style>
