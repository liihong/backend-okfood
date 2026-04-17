<template>
  <view class="page">
    <OkNavbar show-back title="完善会员资料" />
    <scroll-view scroll-y class="scroll" :show-scrollbar="false">
      <view class="wrap">
        <text class="lead">请填写开卡基本信息，便于为您匹配套餐与配送服务。</text>

        <view class="section">
          <text class="sec-title">头像（可选）</text>
          <button class="avatar-btn" open-type="chooseAvatar" @chooseavatar="onChooseAvatar">
            <view class="avatar-box">
              <image
                v-if="avatarUrl"
                class="avatar-img"
                :src="avatarUrl"
                mode="aspectFill"
              />
              <text v-else class="avatar-hint">点击选择头像</text>
            </view>
          </button>
        </view>

        <view class="section">
          <text class="sec-title">昵称 / 用户名</text>
          <view class="nick-wrap">
            <text v-show="showNickHint" class="nick-hint-overlay">微信昵称或常用称呼</text>
            <input
              class="nick-input"
              type="nickname"
              :value="nickDraft"
              placeholder=""
              placeholder-style="color: #64748b;"
              @input="onNickInput"
            />
          </view>
        </view>

        <view class="section">
          <text class="sec-title">购买卡种类（意向）</text>
          <text class="sec-sub">后续支付开通以实际下单为准，此处用于登记意向。</text>
          <view class="plan-grid">
            <view
              :class="['plan-card', selectedPlan === '周卡' ? 'plan-card--on' : '']"
              @click="pickPlan('周卡')"
            >
              <text class="plan-en">WEEKLY</text>
              <text class="plan-name">6天自律周卡</text>
              <!-- <text class="plan-price"><text class="yen">¥</text>168</text> -->
            </view>
            <view
              :class="['plan-card', 'plan-card--rec', selectedPlan === '月卡' ? 'plan-card--on' : '']"
              @click="pickPlan('月卡')"
            >
              <text class="rec">推荐</text>
              <text class="plan-en">MONTHLY</text>
              <text class="plan-name">24 天全能月卡</text>
              <!-- <text class="plan-price"><text class="yen">¥</text>669</text> -->
            </view>
          </view>
        </view>

        <view class="section">
          <text class="sec-title">开始配送日期</text>
          <text class="sec-sub">从该业务日起参与配送排期（与后台上海日历一致）。不可早于今天。</text>
          <picker mode="date" :value="deliveryYmd" :start="minDeliveryYmd" @change="onDeliveryPick">
            <view class="date-picker-row">
              <text
                :class="['date-picker-text', deliveryYmd ? '' : 'date-picker-text--ph']"
              >
                {{ deliveryYmd || '请选择开始配送的日期' }}
              </text>
              <text class="date-picker-arrow">›</text>
            </view>
          </picker>
        </view>

        <button
          class="submit-btn"
          :loading="submitting"
          :disabled="avatarUploading"
          @click="onSubmit"
        >
          保存并返回「我的」
        </button>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { request, getMemberToken, uploadMemberAvatarFile } from '@/utils/api.js'
import { shouldOpenMemberSetup, MEMBER_STUB_NAME, WX_DEFAULT_NICK } from '@/utils/memberProfile.js'

function todayYmd() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const nickDraft = ref('')
/** 展示用：可能是临时路径或已上传的 http(s) 地址 */
const avatarUrl = ref('')
/** 服务端已保存的头像 URL，上传失败时用于恢复展示且不写入非法本地路径 */
const remoteAvatarUrl = ref('')
const selectedPlan = ref('')
const deliveryYmd = ref('')
const minDeliveryYmd = ref(todayYmd())
const submitting = ref(false)
const avatarUploading = ref(false)
const memberPhone = ref('')

const showNickHint = computed(() => !String(nickDraft.value || '').trim())

function pickPlan(p) {
  selectedPlan.value = p
}

onShow(() => {
  minDeliveryYmd.value = todayYmd()
  const phone = uni.getStorageSync('memberPhone') || ''
  memberPhone.value = phone
  if (!getMemberToken() || !phone) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
    return
  }
  void loadProfile()
})

async function loadProfile() {
  const phone = memberPhone.value || uni.getStorageSync('memberPhone') || ''
  if (!phone) return
  try {
    const data = await request('/api/user/me', { method: 'GET' })
    if (!shouldOpenMemberSetup(data)) {
      uni.showToast({ title: '资料已完善', icon: 'success' })
      setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 600)
      return
    }
    const wn = data.wechat_name != null ? String(data.wechat_name).trim() : ''
    const nm = data.name != null ? String(data.name).trim() : ''
    nickDraft.value =
      wn && wn !== WX_DEFAULT_NICK ? wn : nm && nm !== MEMBER_STUB_NAME ? nm : ''
    if (data.avatar_url) {
      const au = String(data.avatar_url).trim()
      avatarUrl.value = au
      remoteAvatarUrl.value = au
    } else {
      avatarUrl.value = ''
      remoteAvatarUrl.value = ''
    }
    const pt = data.plan_type != null ? String(data.plan_type).trim() : ''
    if (pt === '周卡' || pt === '月卡') selectedPlan.value = pt
    const ds = data.delivery_start_date != null ? String(data.delivery_start_date).trim() : ''
    deliveryYmd.value = ds.length >= 10 ? ds.slice(0, 10) : ''
  } catch (e) {
    console.warn('loadProfile', e)
  }
}

function onDeliveryPick(e) {
  deliveryYmd.value = e.detail?.value || ''
}

function isPersistableAvatarUrl(u) {
  const s = String(u || '').trim()
  if (!s) return false
  return /^https?:\/\//i.test(s)
}

async function onChooseAvatar(e) {
  const localPath = e.detail?.avatarUrl
  if (!localPath) return
  avatarUrl.value = localPath
  avatarUploading.value = true
  try {
    uni.showLoading({ title: '上传头像…', mask: true })
    const permanentUrl = await uploadMemberAvatarFile(localPath)
    avatarUrl.value = permanentUrl
    remoteAvatarUrl.value = permanentUrl
  } catch (err) {
    avatarUrl.value = remoteAvatarUrl.value || ''
    uni.showToast({
      title: `${err?.message || '头像上传失败'}，可继续保存其他资料`,
      icon: 'none',
      duration: 2800,
    })
  } finally {
    avatarUploading.value = false
    uni.hideLoading()
  }
}

function onNickInput(e) {
  nickDraft.value = e.detail?.value ?? ''
}

async function onSubmit() {
  const phone = memberPhone.value || uni.getStorageSync('memberPhone') || ''
  const nick = String(nickDraft.value || '').trim()
  if (!nick || nick === WX_DEFAULT_NICK) {
    uni.showToast({ title: '请填写昵称', icon: 'none' })
    return
  }
  if (!selectedPlan.value) {
    uni.showToast({ title: '请选择套餐类型', icon: 'none' })
    return
  }
  const d0 = deliveryYmd.value?.trim()
  if (!d0) {
    uni.showToast({ title: '请选择开始配送日期', icon: 'none' })
    return
  }
  if (d0 < minDeliveryYmd.value) {
    uni.showToast({ title: '起送日不能早于今天', icon: 'none' })
    return
  }
  if (!getMemberToken() || !phone) {
    uni.showToast({ title: '登录已失效', icon: 'none' })
    return
  }
  if (avatarUploading.value) {
    uni.showToast({ title: '头像正在上传，请稍候', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const patch = {
      wechat_name: nick,
      name: nick,
      plan_type: selectedPlan.value,
      delivery_start_date: d0,
    }
    const av = String(avatarUrl.value || '').trim()
    if (isPersistableAvatarUrl(av)) {
      patch.avatar_url = av
    }
    await request('/api/user/profile', {
      method: 'PATCH',
      data: patch,
    })
    const storedAvatar =
      (isPersistableAvatarUrl(av) ? av : remoteAvatarUrl.value || '').trim()
    try {
      uni.setStorageSync(`okfood_wx_profile:${phone}`, {
        nickName: nick,
        avatarUrl: storedAvatar,
      })
    } catch {
      /*忽略 */
    }
    uni.showToast({ title: '已保存', icon: 'success' })
    setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
  } catch (err) {
    uni.showToast({ title: err?.message || '保存失败', icon: 'none' })
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
  margin-bottom: 40rpx;
}

.section {
  margin-bottom: 44rpx;
}

.sec-title {
  display: block;
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-slate-800;
  margin-bottom: 20rpx;
}

.sec-sub {
  display: block;
  font-size: 22rpx;
  color: $ok-slate-500;
  font-weight: 700;
  margin: -8rpx 0 20rpx;
  line-height: 1.4;
}

.avatar-btn {
  padding: 0;
  margin: 0;
  background: transparent;
  border: none;
  line-height: 0;
  display: inline-block;
}

.avatar-btn::after {
  border: none;
}

.avatar-box {
  width: 160rpx;
  height: 160rpx;
  border-radius: 50%;
  background: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 6rpx solid #fff;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  display: block;
}

.avatar-hint {
  font-size: 24rpx;
  font-weight: 800;
  color: $ok-slate-500;
  padding: 16rpx;
  text-align: center;
}

.nick-wrap {
  position: relative;
}

.nick-hint-overlay {
  position: absolute;
  left: 36rpx;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  font-size: 28rpx;
  font-weight: 700;
  color: #64748b;
  z-index: 2;
}

.nick-input {
  position: relative;
  z-index: 1;
  width: 100%;
  background: #f1f5f9;
  border-radius: 999rpx;
  padding: 24rpx 36rpx;
  font-size: 30rpx;
  font-weight: 800;
  color: #0f172a;
  box-sizing: border-box;
  min-height: 88rpx;
}

.plan-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24rpx;
}

.plan-card {
  background: #fff;
  border-radius: 36rpx;
  padding: 36rpx 28rpx;
  border: 3rpx solid $ok-slate-100;
  position: relative;
  min-height: 200rpx;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.plan-card--rec {
  background: #fffdf5;
}

.plan-card--on {
  border-color: $ok-forest-green;
  box-shadow: 0 8rpx 24rpx rgba(14, 90, 68, 0.12);
}

.rec {
  position: absolute;
  top: -14rpx;
  right: 16rpx;
  background: $ok-sunshine-yellow;
  color: $ok-forest-green;
  font-size: 18rpx;
  font-weight: 950;
  padding: 6rpx 14rpx;
  border-radius: 12rpx;
}

.plan-en {
  font-size: 18rpx;
  font-weight: 900;
  color: $ok-slate-400;
}

.plan-name {
  font-size: 28rpx;
  font-weight: 950;
  color: $ok-slate-800;
  margin-top: 8rpx;
}

.plan-price {
  font-size: 40rpx;
  font-weight: 1000;
  font-style: italic;
  color: $ok-forest-green;
  margin-top: 12rpx;
}

.yen {
  font-size: 22rpx;
  font-style: normal;
}

.submit-btn {
  margin-top: 20rpx;
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
</style>
