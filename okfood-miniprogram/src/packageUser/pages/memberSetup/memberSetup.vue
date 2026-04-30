<template>
  <view class="page">
   <OkNavbar show-back :title="resumeOnlyMode ? '恢复配送' : '会员资料与开卡'" />
    <scroll-view scroll-y class="scroll" :show-scrollbar="false">
     <view class="wrap">

      <!-- 从「我的」恢复配送：仅配送方式 + 起送日 -->
      <view v-if="resumeOnlyMode" class="setup-module">
        <view class="section section--resume-only">
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
           <template v-if="deliveryMode === 'delivery' || deliveryMode === 'pickup'">
              <text class="sec-sub">
               <template v-if="deliveryMode === 'delivery'">
                 顺丰小哥全程保驾护航。
               </template>
                <template v-else>
                 OK饭健康餐门店位置：天安名邸小区门面房
                </template>
              </text>
              <picker mode="date" :value="pickerDeliveryYmd" :start="minDeliveryYmd" @change="onDeliveryPick">
                <view class="date-picker-row">
                  <text :class="['date-picker-text', deliveryYmd ? '' : 'date-picker-text--ph']">
                   {{ deliveryYmd || '请选择开始的业务日期' }}
                  </text>
                  <text class="date-picker-arrow">›</text>
                </view>
              </picker>
            </template>
            <text v-else class="sec-sub">
             请在上方选择「配送到家」或「门店自提」，并选择开始的业务日期。
            </text>
          </view>
      </view>

      <view v-else class="setup-module">
         <text class="module-title">一、个人资料</text>
          <view v-if="!skipProfileIdentityEdit" class="section">
            <text class="sec-title">头像（可选）</text>
            <button class="avatar-btn" open-type="chooseAvatar" @chooseavatar="onChooseAvatar">
              <view class="avatar-box">
                <image v-if="avatarUrl" class="avatar-img" :src="avatarUrl" mode="aspectFill" />
                <text v-else class="avatar-hint">点击选择头像</text>
              </view>
            </button>
          </view>

        <view v-if="!skipProfileIdentityEdit" class="section">
            <text class="sec-title">昵称 / 用户名</text>
            <view class="nick-wrap">
              <text v-show="showNickHint" class="nick-hint-overlay">微信昵称或常用称呼</text>
              <input class="nick-input" type="nickname" :value="nickDraft" placeholder=""
                placeholder-style="color: #64748b;" @input="onNickInput" />
            </view>
          </view>

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
              <label v-if="!resumeOnlyMode" class="pay-radio-row">
                <radio value="defer" :checked="deliveryMode === 'defer'" :color="payRadioColor" />
                <text class="pay-radio-label">暂停配送</text>
              </label>
            </radio-group>
           <template v-if="deliveryMode === 'delivery' || deliveryMode === 'pickup'">
              <text class="sec-sub">
               <template v-if="deliveryMode === 'delivery'">
                 顺丰小哥全程保驾护航。
               </template>
                <template v-else>
                 OK饭健康餐门店位置：天安名邸小区门面房
                </template>
              </text>
              <picker mode="date" :value="pickerDeliveryYmd" :start="minDeliveryYmd" @change="onDeliveryPick">
                <view class="date-picker-row">
                  <text :class="['date-picker-text', deliveryYmd ? '' : 'date-picker-text--ph']">
                   {{ deliveryYmd || '请选择开始的业务日期' }}
                  </text>
                  <text class="date-picker-arrow">›</text>
                </view>
              </picker>
            </template>
            <text v-else class="sec-sub">
             暂停配送后剩余次数保留；恢复时在「我的」点「恢复配送」或在此改选配送方式与日期。
            </text>
          </view>

        <view class="section">
          <text class="sec-title">每日送达数量</text>
          <text class="sec-sub">
            每个配送日需送达的份数；确认送达时按此倍数从剩余次数中扣减（1～20 份）。
          </text>
          <view class="units-stepper">
            <button
              class="units-stepper-btn"
              :disabled="dailyMealUnits <= 1"
              @click="bumpDailyUnits(-1)"
            >
              -
            </button>
            <text class="units-stepper-value">{{ dailyMealUnits }}</text>
            <button
              class="units-stepper-btn"
              :disabled="dailyMealUnits >= 20"
              @click="bumpDailyUnits(1)"
            >
              +
            </button>
          </view>
        </view>
       </view>

        <view v-if="!resumeOnlyMode && needsCardPayment" class="setup-module setup-module--card">
         <text class="module-title">二、开卡</text>
          <view class="section">
           <text class="sec-title">开卡卡种</text>
            <text class="sec-sub">
             请选择您已经付费的卡种
            </text>
            <view class="plan-premium-wrap">
              <view class="plan-grid plan-grid--premium">
                <view :class="['plan-card', 'plan-card--premium', selectedPlan === '周卡' ? 'plan-card--on' : '']"
                  @click="pickPlan('周卡')">
                  <view v-if="selectedPlan === '周卡'" class="plan-picked-pill">
                    <text class="plan-picked-pill-txt">已选</text>
                  </view>
                  <text class="plan-headline">自律周卡 / 6天</text>
                  <text class="plan-origin">原价 ¥{{ cardOrigWeek }}</text>
                  <view class="plan-activity">
                    <view class="plan-activity-tag">
                      <text class="plan-activity-tag-line">活</text>
                      <text class="plan-activity-tag-line">动</text>
                      <text class="plan-activity-tag-line">价</text>
                    </view>
                    <view class="plan-activity-amount">
                      <text class="pa-yen">¥</text>
                      <text class="pa-num">{{ cardPriceWeek }}</text>
                    </view>
                  </view>
                  <view class="plan-save">立省 ¥{{ saveAmountWeek }}</view>
                  <view class="plan-card-dash" />
                  <text class="plan-footnote">轻盈重启首选</text>
                </view>
                <view
:class="[
                  'plan-card',
                  'plan-card--premium',
                  'plan-card--rec',
                  selectedPlan === '月卡' ? 'plan-card--on' : '',
                ]" @click="pickPlan('月卡')">
                  <view v-if="selectedPlan === '月卡'" class="plan-picked-pill">
                    <text class="plan-picked-pill-txt">已选</text>
                  </view>
                  <text class="plan-rec-pill">推荐</text>
                  <text class="plan-headline">全能月卡 / 24天</text>
                  <text class="plan-origin">原价 ¥{{ cardOrigMonth }}</text>
                  <view class="plan-activity">
                    <view class="plan-activity-tag">
                      <text class="plan-activity-tag-line">活</text>
                      <text class="plan-activity-tag-line">动</text>
                      <text class="plan-activity-tag-line">价</text>
                    </view>
                    <view class="plan-activity-amount">
                      <text class="pa-yen">¥</text>
                      <text class="pa-num">{{ cardPriceMonth }}</text>
                    </view>
                  </view>
                  <view class="plan-save">立省 ¥{{ saveAmountMonth }}</view>
                  <view class="plan-card-dash" />
                  <text class="plan-footnote">终极管理方案</text>
                </view>
              </view>
            </view>
         </view>
          <view class="section">
            <text class="sec-title">线下已缴说明</text>
            <text class="sec-sub">
             信息提交后，由客服审核确认，并开始安排配送。
            </text>
          </view>
        </view>

        <view v-else-if="!resumeOnlyMode && !needsCardPayment" class="section">
          <text class="sec-title">会员状态</text>
          <text class="sec-sub">
            您当前仍有剩余订餐次数（{{ serverBalance }} 次），无需再次购买会员卡，完善资料即可。
          </text>
        </view>

        <button
          class="submit-btn"
          :loading="submitting"
          :disabled="avatarUploading"
          @click="onSubmit"
        >
          {{ submitButtonText }}
        </button>
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
  uploadMemberAvatarFile,
  clearMemberSession,
  isUserMeNotFoundError,
} from '@/utils/api.js'
import {
  shouldOpenMemberSetup,
  shouldPromptMemberCardPay,
  MEMBER_STUB_NAME,
  WX_DEFAULT_NICK,
} from '@/utils/memberProfile.js'
import { minMemberDeliveryStartYmd } from '@/utils/menuApi.js'

/** 与 uni.scss $ok-forest-green 一致，供 radio 组件 color 使用 */
const payRadioColor = '#0e5a44'

const nickDraft = ref('')
/** 展示用：可能是临时路径或已上传的 http(s) 地址 */
const avatarUrl = ref('')
/** 服务端已保存的头像 URL，上传失败时用于恢复展示且不写入非法本地路径 */
const remoteAvatarUrl = ref('')
const selectedPlan = ref('周卡')
/** 需购卡时：固定为线下已缴，仅保存资料并提交卡种（不拉起微信支付） */
/** delivery=配送到家；pickup=门店自提；defer=暂停配送（服务端 delivery_deferred） */
const deliveryMode = ref('delivery')
const deliveryYmd = ref('')
const minDeliveryYmd = ref(minMemberDeliveryStartYmd())
/** 每配送日份数，与 members.daily_meal_units 一致；自助范围 1～20 */
const dailyMealUnits = ref(1)
const submitting = ref(false)
const avatarUploading = ref(false)
const memberPhone = ref('')
const serverBalance = ref(0)
/** 与后台 app_settings 同步，请求失败时用默认展示 */
const cardPriceWeek = ref('168')
const cardPriceMonth = ref('669')
/** 展示用划线价；可与接口价同步，缺省为常见标价 */
const cardOrigWeek = ref('188')
const cardOrigMonth = ref('699')
/** 资料已完备、仅开卡续费时隐藏头像与昵称编辑（与 shouldOpenMemberSetup 判定一致） */
const skipProfileIdentityEdit = ref(false)

const showNickHint = computed(() => !String(nickDraft.value || '').trim())

/** 未选日期时让滚轮落在合法最小日上，避免默认停在「今天」却仍受 start 限制 */
const pickerDeliveryYmd = computed(() => deliveryYmd.value || minDeliveryYmd.value)

const saveAmountWeek = computed(() => {
  const o = Math.floor(Number(cardOrigWeek.value) || 0)
  const c = Math.floor(Number(cardPriceWeek.value) || 0)
  return Math.max(0, o - c)
})
const saveAmountMonth = computed(() => {
  const o = Math.floor(Number(cardOrigMonth.value) || 0)
  const c = Math.floor(Number(cardPriceMonth.value) || 0)
  return Math.max(0, o - c)
})

const needsCardPayment = computed(() => serverBalance.value <= 0)

const submitButtonText = computed(() => {
  if (resumeOnlyMode.value) return '确认恢复配送'
  if (!needsCardPayment.value) return '保存并返回「我的」'
  return '保存资料'
})

function pickPlan(p) {
  if (p === '周卡' || p === '月卡') {
    selectedPlan.value = p
  }
}

function bumpDailyUnits(delta) {
  const n = Math.floor(Number(dailyMealUnits.value) || 1) + delta
  dailyMealUnits.value = Math.max(1, Math.min(20, n))
}

function onDeliveryModeChange(e) {
  const v = e?.detail?.value
  if (v === 'defer') {
    deliveryMode.value = 'defer'
    deliveryYmd.value = ''
  } else if (v === 'pickup') {
    deliveryMode.value = 'pickup'
  } else {
    deliveryMode.value = 'delivery'
  }
}

/** 从「我的」恢复配送进入：仅展示配送方式与起送日 */
const resumeOnlyMode = ref(false)
const resumeHintShown = ref(false)

onLoad((options) => {
  const raw = options?.preCard != null ? String(options.preCard) : ''
  const k = decodeURIComponent(raw).trim()
  if (k === '周卡' || k === '月卡') {
    selectedPlan.value = k
  }
  const fr = options?.from != null ? String(options.from).trim() : ''
  resumeOnlyMode.value = fr === 'resume'
  resumeHintShown.value = false
})

onShow(() => {
  minDeliveryYmd.value = minMemberDeliveryStartYmd()
  if (deliveryYmd.value && deliveryYmd.value < minDeliveryYmd.value) {
    deliveryYmd.value = ''
  }
  const phone = uni.getStorageSync('memberPhone') || ''
  memberPhone.value = phone
  if (!getMemberToken() || !phone) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
    return
  }
  void loadCardPrices()
  void loadProfile()
})

async function loadCardPrices() {
  if (!getMemberToken()) return
  try {
    const d = await request('/api/user/member-card-prices', { method: 'GET' })
    if (d && typeof d === 'object') {
      const w = d.week_price_yuan != null ? String(d.week_price_yuan).trim() : ''
      const m = d.month_price_yuan != null ? String(d.month_price_yuan).trim() : ''
      if (w) cardPriceWeek.value = w
      if (m) cardPriceMonth.value = m
    }
  } catch {
    /* 使用页面默认值 */
  }
}

async function loadProfile() {
  const phone = memberPhone.value || uni.getStorageSync('memberPhone') || ''
  if (!phone) return
  skipProfileIdentityEdit.value = false
  try {
    const data = await request('/api/user/me', { method: 'GET' })
    minDeliveryYmd.value = minMemberDeliveryStartYmd()
    serverBalance.value = Math.max(0, Math.floor(Number(data.balance) || 0))
    skipProfileIdentityEdit.value =
      shouldPromptMemberCardPay(data) && !shouldOpenMemberSetup(data)
    /** 有余额且暂停配送时仍须停留本页以便改为「恢复配送」并重选起送日 */
    const pausedWithBalance =
      data.delivery_deferred === true && serverBalance.value > 0
    if (!shouldOpenMemberSetup(data) && !shouldPromptMemberCardPay(data) && !pausedWithBalance) {
      uni.showToast({ title: '资料与餐次已就绪', icon: 'success' })
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
    dailyMealUnits.value = Math.max(
      1,
      Math.min(20, Math.floor(Number(data.daily_meal_units) || 1)),
    )
    if (data.delivery_deferred === true) {
      deliveryMode.value = 'defer'
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
  } catch (e) {
    skipProfileIdentityEdit.value = false
    if (isUserMeNotFoundError(e)) {
      clearMemberSession()
      uni.showToast({ title: '登录已失效，请重新登录', icon: 'none' })
      setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
      return
    }
    console.warn('loadProfile', e)
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

  if (resumeOnlyMode.value) {
    if (!getMemberToken() || !phone) {
      uni.showToast({ title: '登录已失效', icon: 'none' })
      return
    }
    if (deliveryMode.value === 'defer') {
      uni.showToast({ title: '请选择配送到家或门店自提', icon: 'none' })
      return
    }
    const d0 = deliveryYmd.value?.trim()
    if (!d0) {
      uni.showToast({ title: '请选择开始的业务日期', icon: 'none' })
      return
    }
    if (d0 < minDeliveryYmd.value) {
      uni.showToast({
        title: '起送日须不早于当前允许的最小业务日（上海；10:00 前可今日起，10:00 后仅次日起）',
        icon: 'none',
      })
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
      uni.showToast({ title: '已恢复配送', icon: 'success', duration: 2000 })
      setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
    } catch (err) {
      uni.hideLoading()
      uni.showToast({ title: err?.message || '保存失败', icon: 'none', duration: 2800 })
    } finally {
      submitting.value = false
    }
    return
  }

  if (
    !skipProfileIdentityEdit.value &&
    (!nick || nick === WX_DEFAULT_NICK)
  ) {
    uni.showToast({ title: '请填写昵称', icon: 'none' })
    return
  }
  if (needsCardPayment.value && !selectedPlan.value) {
    uni.showToast({ title: '请选择周卡或月卡', icon: 'none' })
    return
  }
  const d0 = deliveryYmd.value?.trim()
  if (deliveryMode.value === 'delivery' || deliveryMode.value === 'pickup') {
    if (!d0) {
      uni.showToast({ title: '请选择开始的业务日期', icon: 'none' })
      return
    }
    if (d0 < minDeliveryYmd.value) {
      uni.showToast({
        title: '起送日须不早于当前允许的最小业务日（上海；10:00 前可今日起，10:00 后仅次日起）',
        icon: 'none',
      })
      return
    }
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
    }
    if (deliveryMode.value === 'defer') {
      patch.delivery_deferred = true
    } else {
      patch.delivery_deferred = false
      patch.delivery_start_date = d0
      patch.store_pickup = deliveryMode.value === 'pickup'
    }
    if (needsCardPayment.value) {
      patch.card_pay_mode = 'offline_paid'
      patch.plan_type = selectedPlan.value === '月卡' ? '月卡' : '周卡'
    }
    const av = String(avatarUrl.value || '').trim()
    if (isPersistableAvatarUrl(av)) {
      patch.avatar_url = av
    }
    patch.daily_meal_units = Math.max(
      1,
      Math.min(20, Math.floor(Number(dailyMealUnits.value) || 1)),
    )
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

    const t =
      needsCardPayment.value &&
        (deliveryMode.value === 'delivery' || deliveryMode.value === 'pickup')
        ? '已保存。后台开卡工单待核对'
        : '已保存'
    uni.showToast({
      title: t,
      icon: 'success',
      duration:
        needsCardPayment.value &&
          (deliveryMode.value === 'delivery' || deliveryMode.value === 'pickup')
          ? 2200
          : 2000,
    })
    setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
  } catch (err) {
    uni.hideLoading()
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
  margin-bottom: 40rpx;
}

.setup-module {
  margin-bottom: 32rpx;
  padding: 28rpx 24rpx 8rpx;
  background: #fff;
  border-radius: 24rpx;
  border: 2rpx solid $ok-slate-100;
  box-sizing: border-box;
}

.setup-module--card {
  padding-bottom: 20rpx;
}

.module-title {
  display: block;
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-forest-green;
  margin-bottom: 8rpx;
  padding-bottom: 16rpx;
  border-bottom: 2rpx solid $ok-slate-100;
}

.setup-module--card .module-title {
  border-bottom-color: rgba(14, 90, 68, 0.15);
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

.plan-premium-wrap {
  margin-top: 24rpx;
  background: $ok-forest-green;
  padding: 32rpx 20rpx;
  border-radius: 36rpx;
  box-sizing: border-box;
}
.plan-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20rpx;
}

.plan-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  box-sizing: border-box;
  }
  
  .plan-card--premium {
    background: #fff;
    border-radius: 48rpx;
    padding: 32rpx 20rpx 24rpx;
    border: 3rpx solid rgba(255, 255, 255, 0.55);
    min-height: 0;
    transition:
      border-color 0.18s ease,
      box-shadow 0.18s ease,
      background 0.18s ease,
      transform 0.18s ease;
  }
  
  .plan-card--rec.plan-card--premium {
    background: #fff;
  }
  
  .plan-card--premium.plan-card--on {
  border: 6rpx solid #ffd869;
    background: linear-gradient(180deg, #f4fbf7 0%, #ffffff 42%, #ffffff 100%);
    box-shadow:
      0 0 0 4rpx rgba(14, 90, 68, 0.14),
      0 8rpx 0 rgba(14, 90, 68, 0.06),
      0 20rpx 40rpx rgba(14, 90, 68, 0.18);
    transform: scale(1.02);
    z-index: 1;
}

.plan-picked-pill {
  position: absolute;
  top: 10rpx;
  left: 10rpx;
  z-index: 3;
  background: $ok-forest-green;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  line-height: 1;
  box-shadow: 0 4rpx 12rpx rgba(14, 90, 68, 0.35);
}

.plan-picked-pill-txt {
  font-size: 20rpx;
  font-weight: 950;
  color: #fff;
  letter-spacing: 0.5rpx;
}

.plan-rec-pill {
  position: absolute;
  top: 12rpx;
  right: 12rpx;
    z-index: 2;
  background: $ok-sunshine-yellow;
  color: $ok-forest-green;
  font-size: 18rpx;
  font-weight: 950;
  padding: 6rpx 14rpx;
  border-radius: 999rpx;
}

.plan-headline {
  display: block;
  text-align: center;
  font-size: 28rpx;
  font-weight: 950;
  color: $ok-forest-green;
  line-height: 1.35;
  padding: 0 8rpx;
  margin-top: 8rpx;
}
.plan-origin {
  display: block;
  text-align: center;
  font-size: 24rpx;
  font-weight: 700;
  color: #94a3b8;
  text-decoration: line-through;
  margin-top: 12rpx;
}

.plan-activity {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  background: #e6f4ef;
  border-radius: 20rpx;
  overflow: hidden;
  margin-top: 16rpx;
}

.plan-activity-tag {
  background: $ok-forest-green;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12rpx 8rpx;
  flex-shrink: 0;
}

.plan-activity-tag-line {
  font-size: 20rpx;
  font-weight: 800;
  color: #fff;
  line-height: 1.12;
}

.plan-activity-amount {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: baseline;
  justify-content: center;
  padding: 14rpx 12rpx 18rpx;
}

.pa-yen {
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-forest-green;
}

.pa-num {
  font-size: 46rpx;
  font-weight: 1000;
  color: $ok-forest-green;
  line-height: 1;
  margin-left: 4rpx;
  }
  
  .plan-save {
    align-self: center;
    margin-top: 16rpx;
    background: #e63946;
    color: #fff;
    font-size: 22rpx;
    font-weight: 950;
    padding: 10rpx 32rpx;
    border-radius: 999rpx;
    box-shadow: 0 6rpx 16rpx rgba(230, 57, 70, 0.3);
  }
  
  .plan-card-dash {
    height: 0;
    border-top: 2rpx dashed #cbd5e1;
    margin: 20rpx 4rpx 12rpx;
}

.plan-footnote {
  display: block;
  text-align: center;
  font-size: 22rpx;
  font-weight: 700;
  color: #64748b;
    line-height: 1.4;
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

.units-stepper {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 28rpx;
  padding: 8rpx 0 4rpx;
}

.units-stepper-btn {
  min-width: 88rpx;
  height: 88rpx;
  padding: 0;
  margin: 0;
  line-height: 86rpx;
  text-align: center;
  font-size: 40rpx;
  font-weight: 900;
  color: $ok-forest-green;
  background: #f1f5f9;
  border: 3rpx solid $ok-slate-100;
  border-radius: 20rpx;
  box-sizing: border-box;
}

.units-stepper-btn::after {
  border: none;
}

.units-stepper-btn[disabled] {
  opacity: 0.35;
  color: $ok-slate-500;
}

.units-stepper-value {
  min-width: 100rpx;
  text-align: center;
  font-size: 40rpx;
  font-weight: 950;
  color: $ok-slate-800;
}
</style>
