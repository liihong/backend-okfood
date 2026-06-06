<template>
  <view class="page-shell">
  <view class="page" :style="pageStyle">
    <scroll-view
      scroll-y
      class="scroll"
      :style="scrollStyle"
      :show-scrollbar="false"
      refresher-enabled
      :refresher-triggered="refresherTriggered"
      @refresherrefresh="onMineRefresherRefresh"
    >
      <view class="profile-container" :style="profileContainerStyle">
        <!-- 未登录 -->
        <view v-if="!isLoggedIn" class="mine-hero mine-hero--guest">
          <view class="hero-guest-inner">
            <view class="avatar-ring avatar-ring--guest">
              <text class="avatar-fallback">?</text>
            </view>
            <view class="hero-guest-copy">
              <button
                class="wx-login-btn"
                hover-class="wx-login-btn--hover"
                open-type="getPhoneNumber"
                @getphonenumber="onWxGetPhoneNumber"
              >
                手机号登录
              </button>
              <text class="guest-hint">授权后与会员档案、餐次同步</text>
            </view>
          </view>
        </view>

        <!-- 已登录：参考稿式头部 + 数据卡片 + 宫格 -->
        <template v-else>
          <view
            class="mine-hero"
            :class="{ 'mine-hero--tap': needsMemberSetupPage }"
            @tap="onMineHeroTap"
          >
            <view class="hero-avatar-row">
              <view class="hero-avatar-wrap">
                <view v-if="needsMemberSetupPage" class="hero-avatar-btn hero-avatar-btn--static">
                  <view class="avatar-ring">
                    <text class="avatar-fallback-sm">配</text>
                  </view>
                </view>
                <button
                  v-else
                  class="hero-avatar-btn"
                  open-type="chooseAvatar"
                  @chooseavatar="onChooseAvatar"
                >
                  <view class="avatar-ring">
                    <image
                      v-if="wxProfile?.avatarUrl"
                      class="avatar-img"
                      :src="wxProfile.avatarUrl"
                      mode="aspectFill"
                    />
                    <text v-else class="avatar-fallback-sm">{{ avatarChar }}</text>
                  </view>
                </button>
              </view>
            </view>
            <view
              class="hero-nick-wrap"
              :class="{ 'hero-nick-wrap--action': needsMemberSetupPage }"
              @tap.stop="onNickWrapTap"
            >
              <text
                class="hero-nick"
                :class="{
                  'hero-nick--action': needsMemberSetupPage,
                  'hero-nick--editable': !needsMemberSetupPage,
                }"
              >
                {{ needsMemberSetupPage ? setupRowTitle : displayNick }}
              </text>
              <text v-if="!needsMemberSetupPage" class="hero-nick-edit">✎</text>
            </view>
            <view class="hero-phone-row" @tap.stop>
              <text class="hero-phone">{{ displayPhone }}</text>
              <view class="hero-gear" @tap.stop="goMemberSetup">
                <text class="hero-gear-icon">⚙</text>
              </view>
            </view>
          </view>
        </template>

        <MinePlanStatusCard
          :remaining-meals="planCardRemainingMeals"
          :status-text="memberDeliveryStatus"
          :status-alert="planCardStatusAlert"
          :footer-tagline="cardFooter"
          :plan-kind="planType"
          :plan-label="planTypeMemberLabel"
          :address-line="planCardAddressLine"
          :show-resume-chip="showResumeDeliveryEntry"
          :show-setup-delivery-chip="showSetupDeliveryChip"
          :show-buy-card-chip="showBuyCardChip"
          @resume="goResumeDelivery"
          @setup-delivery="goMemberSetup"
          @buy-card="goMembershipCardPack"
        />

        <template v-if="isLoggedIn">
          <text class="section-cap section-cap--sp">个人自律管理</text>
          <view class="menu-card">
            <view class="menu-grid">
              <view class="menu-cell" @tap="goMembershipCardPack">
                <view class="menu-ico-wrap">
                  <image
                    class="menu-ico-img"
                    src="/static/mine-icons/credit-card-light.svg"
                    mode="aspectFit"
                  />
                </view>
                <text class="menu-cap">点我购卡</text>
              </view>
              <view class="menu-cell" @tap="goMyCoupons">
                <view class="menu-ico-wrap">
                  <image
                    class="menu-ico-img"
                    src="/static/mine-icons/ticket.svg"
                    mode="aspectFit"
                  />
                </view>
                <text class="menu-cap">我的优惠券</text>
              </view>
              <view v-if="showDouyinRedeemMenu" class="menu-cell" @tap="goDouyinRedeem">
                <view class="menu-ico-wrap">
                  <image
                    class="menu-ico-img"
                    src="/static/mine-icons/activity.svg"
                    mode="aspectFit"
                  />
                </view>
                <text class="menu-cap">抖音验券</text>
              </view>
              <view class="menu-cell" @tap="goMyOrders">
                <view class="menu-ico-wrap">
                  <image
                    class="menu-ico-img"
                    src="/static/mine-icons/clipboard-list.svg"
                    mode="aspectFit"
                  />
                </view>
                <text class="menu-cap">我的订单</text>
              </view>
              <view class="menu-cell" @tap="goDailyMealUnits">
                <view class="menu-ico-wrap">
                  <image
                    class="menu-ico-img"
                    src="/static/mine-icons/truck.svg"
                    mode="aspectFit"
                  />
                </view>
                <text class="menu-cap">份数管理</text>
              </view>
              <view class="menu-cell" @tap="goLeave">
                <view class="menu-ico-wrap">
                  <image
                    class="menu-ico-img"
                    src="/static/mine-icons/calendar.svg"
                    mode="aspectFit"
                  />
                </view>
                <text class="menu-cap">请假管理</text>
              </view>
              <view class="menu-cell" @tap="goAddress">
                <view class="menu-ico-wrap">
                  <image
                    class="menu-ico-img"
                    src="/static/mine-icons/map-pin.svg"
                    mode="aspectFit"
                  />
                </view>
                <text class="menu-cap">地址管理</text>
              </view>
              <view class="menu-cell" @tap="goSingleOrders">
                <view class="menu-ico-wrap">
                  <image
                    class="menu-ico-img"
                    src="/static/mine-icons/file-text.svg"
                    mode="aspectFit"
                  />
                </view>
                <text class="menu-cap">消费记录</text>
              </view>
            </view>
            <view v-if="showPauseDeliveryMenuRow" class="menu-extra" @tap="onPauseDeliveryTap">
              <text class="menu-extra-txt">⏸ 暂停配送（保留剩余餐次）</text>
              <text class="menu-extra-arr">›</text>
            </view>
          </view>
        </template>

      <text class="page-version">Version 2.1.8 · 火源文化技术支持</text>
      </view>
    </scroll-view>

    <!-- 微信昵称编辑弹层 -->
    <view v-if="showNickEditor" class="nick-mask" @tap="closeNickEditor">
      <view class="nick-sheet" @tap.stop>
        <text class="nick-sheet-title">设置昵称</text>
        <text class="nick-sheet-hint">点击输入框，键盘可一键填入微信昵称</text>
        <input
          class="nick-sheet-input"
          type="nickname"
          :value="wxNickDraft"
          :focus="nickInputFocus"
          placeholder="请输入或选用微信昵称"
          placeholder-class="nick-sheet-ph"
          maxlength="32"
          confirm-type="done"
          @input="onNickInput"
          @confirm="confirmNickEdit"
        />
        <view class="nick-sheet-actions">
          <button class="nick-sheet-btn nick-sheet-btn--ghost" @tap="closeNickEditor">取消</button>
          <button class="nick-sheet-btn nick-sheet-btn--primary" @tap="confirmNickEdit">保存</button>
        </view>
      </view>
    </view>
  </view>
  <OkAlertHost />
  </view>
</template>

<script setup>
import OkAlertHost from '@/components/OkAlertHost/OkAlertHost.vue'
import { showOkAlert } from '@/utils/okAlert.js'
import { ref, computed, onMounted, nextTick } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import MinePlanStatusCard from '@/components/MinePlanStatusCard/MinePlanStatusCard.vue'
import {
  request,
  getMemberToken,
  getCourierToken,
  setAppUserMode,
  reLaunchIfCourierModePreferred,
  uploadMemberAvatarFile,
  clearMemberSession,
  isUserMeNotFoundError,
} from '@/utils/api.js'
import { wxMiniMemberLoginAndStore, hasWxPhoneAuthDetail } from '@/utils/wxMemberLogin.js'
import {
  shouldOpenMemberSetup,
  shouldCompleteMemberProfile,
  shouldPromptMemberCardPay,
  isDeliveryPausedWithBalance,
  isMemberInActiveDelivery,
  isMemberDeliveryScheduledFuture,
  MEMBER_STUB_NAME,
  WX_DEFAULT_NICK,
} from '@/utils/memberProfile.js'
import { getTabPageLayoutStyles } from '@/utils/tabPageLayout.js'
import { getNavbarLayout } from '@/utils/navbar.js'
import { syncCustomTabBar } from '@/utils/customTabBar.js'
import {
  normalizeAddressList,
  addressListRow,
  sortAddressesDefaultFirst,
  isAddressItemDefault,
} from '@/utils/addressApi.js'
import { consumeMinePageNeedsRefresh, markMinePageNeedsRefresh } from '@/utils/minePageRefresh.js'

/** 抖音验券入口：下一版再开放 */
const showDouyinRedeemMenu = false
import { guardMemberDeliverySelfService } from '@/utils/memberSelfServiceGuard.js'
import { ymdTodayShanghai } from '@/utils/memberDeliveryDate.js'
import {
  ymdFromApi,
  ymdToCnMd,
  isOnLeaveTodayShanghai,
  isLeaveRangeActiveOrFuture,
  isTomorrowLeaveActive,
} from '@/utils/memberLeaveDisplay.js'

const pageStyle = ref({})
const scrollStyle = ref({})
const profileContainerStyle = ref({})

function syncTabLayout() {
  const { pageStyle: p, scrollStyle: s } = getTabPageLayoutStyles({ fullBleed: true })
  const { statusBarHeight } = getNavbarLayout()
  pageStyle.value = p
  scrollStyle.value = s
  profileContainerStyle.value = {
    paddingTop: `${statusBarHeight + 12}px`,
  }
}

const DEMO_MEAL_KEY = 'okfood_demo_meal_credits'
/** 微信头像昵称（按手机号分 key，等同 H5 localStorage 分用户存储） */
const WX_PROFILE_PREFIX = 'okfood_wx_profile'
const isLoggedIn = ref(false)
const memberPhone = ref('')
const wxProfile = ref(null)
/** 昵称输入（type=nickname 可走微信键盘同步） */
const wxNickDraft = ref('')
const showNickEditor = ref(false)
const nickInputFocus = ref(false)
const serverBalance = ref(0)
const userName = ref('')
const planType = ref('')
const leaveRange = ref(null)
/** 与后端 is_leaved_tomorrow 同步：仅明日请假（自提交当日至目标日 24:00 前展示「请假中」） */
const isLeavedTomorrow = ref(false)
/** 与 backend tomorrow_leave_target_date 一致，用于单日快速请假侧展示目标业务日 */
const tomorrowLeaveTargetYmd = ref('')
const isActive = ref(false)
const createdAt = ref('')
/** 每配送日需送达份数（与 /api/user/me.daily_meal_units 一致） */
const dailyMealUnits = ref(1)
/** 与界面同步的剩余餐次（含滚动动画） */
const displayBalance = ref(0)
/** 陪伴天数、每日份数展示用（含滚动动画） */
const displayCompanionDays = ref(0)
const displayDailyUnitsAnim = ref(1)
/** 默认配送地址展示行（详细地址，与地址列表一致，不含所属片区） */
const defaultAddrLine = ref('')
/** 防并发 onShow / 下拉刷新竞态，仅应用最新一次拉取结果 */
let refreshMemberSeq = 0
/** 避免资料完善页与「我的」onShow 重复跳转 */
let profileCompleteNavLock = false
const refresherTriggered = ref(false)

async function syncDefaultAddressForCard(seq) {
  if (!getMemberToken()) {
    if (seq === refreshMemberSeq) defaultAddrLine.value = ''
    return
  }
  try {
    const data = await request('/api/user/me/addresses', { method: 'GET' })
    if (seq !== refreshMemberSeq) return
    const sorted = sortAddressesDefaultFirst(normalizeAddressList(data))
    const defItem = sorted.find((item) => isAddressItemDefault(item))
    const row = defItem ? addressListRow(defItem, 0) : null
    defaultAddrLine.value = row?.line?.trim() || ''
  } catch {
    if (seq !== refreshMemberSeq) return
    defaultAddrLine.value = ''
  }
}

function getDemoCredits() {
  try {
    const n = Number(uni.getStorageSync(DEMO_MEAL_KEY))
    return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0
  } catch {
    return 0
  }
}

function addDemoCredits(amt) {
  const next = getDemoCredits() + amt
  uni.setStorageSync(DEMO_MEAL_KEY, next)
  return next
}

function daysSinceCreated(iso) {
  if (!iso) return 0
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return 0
  return Math.max(0, Math.floor((Date.now() - t) / 86400000))
}

function nextFrame(cb) {
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(cb)
  } else {
    setTimeout(cb, 16)
  }
}

/** 数字递增至 target（计划卡剩余餐次、陪伴天数、每日份数等） */
function animateNumberTo(refObj, target, duration = 720) {
  const to = Math.max(0, Math.floor(Number(target) || 0))
  const from = Math.max(0, Math.floor(Number(refObj.value) || 0))
  if (from === to) return
  const t0 = Date.now()
  const step = () => {
    const elapsed = Date.now() - t0
    const t = Math.min(1, elapsed / duration)
    const eased = 1 - (1 - t) ** 3
    refObj.value = Math.round(from + (to - from) * eased)
    if (t < 1) nextFrame(step)
    else refObj.value = to
  }
  nextFrame(step)
}

/** @param {{ animate?: boolean }} [options] */
function syncPlanCardDisplay(options = {}) {
  const { animate = false } = options
  if (!isLoggedIn.value) {
    displayBalance.value = 0
    displayCompanionDays.value = 0
    displayDailyUnitsAnim.value = 1
    return
  }
  const balanceTotal = Math.max(0, serverBalance.value + getDemoCredits())
  const days = daysSinceCreated(createdAt.value)
  const n = Math.floor(Number(dailyMealUnits.value) || 0)
  const units = n >= 1 ? Math.min(50, n) : 1
  if (animate) {
    animateNumberTo(displayBalance, balanceTotal)
    animateNumberTo(displayCompanionDays, days)
    animateNumberTo(displayDailyUnitsAnim, units)
    return
  }
  displayBalance.value = balanceTotal
  displayCompanionDays.value = days
  displayDailyUnitsAnim.value = units
}

const profileName = computed(() => {
  if (userName.value?.trim()) return userName.value.trim()
  const p = String(memberPhone.value || '').trim()
  if (p) return p
  return '会员'
})

/** 服务端档案缺项时引导至完善资料页 */
const memberProfileRaw = ref(null)

const needsMemberSetupPage = computed(() => {
  if (!isLoggedIn.value) return false
  return shouldOpenMemberSetup(memberProfileRaw.value)
})

/** 无剩余餐次：计划卡展示「去购卡」按钮，不展示每日份数 */
const showMemberCardModule = computed(() => {
  if (!isLoggedIn.value) return false
  const p = memberProfileRaw.value
  if (p && typeof p === 'object') return shouldPromptMemberCardPay(p)
  return serverBalance.value <= 0
})

/** 未完善资料时不展示购卡按钮（优先引导完善配送） */
const showBuyCardChip = computed(() => {
  if (!isLoggedIn.value || needsMemberSetupPage.value) return false
  return showMemberCardModule.value
})

/** 待完善配送/自提：计划卡展示「设置配送信息」按钮 */
const showSetupDeliveryChip = computed(() => {
  if (!isLoggedIn.value) return false
  return needsMemberSetupPage.value
})

/** 有余额且暂停配送：计划卡上展示「恢复配送」（资料待完善也可点此进入资料页恢复） */
const showResumeDeliveryEntry = computed(() => {
  if (!isLoggedIn.value) return false
  return isDeliveryPausedWithBalance(memberProfileRaw.value)
})

/** 仍有餐次且当前未暂停：菜单中提供一键暂停（等同资料页「暂停配送」选项） */
const showPauseDeliveryMenuRow = computed(() => {
  if (!isLoggedIn.value || needsMemberSetupPage.value) return false
  const p = memberProfileRaw.value
  if (!p || typeof p !== 'object') return false
  if (p.delivery_deferred === true) return false
  return Math.max(0, Math.floor(Number(p.balance) || 0)) > 0
})

/** 备餐锁窗内且已在履约日配送大表：禁止暂停（与后端 pause_delivery_prep_locked 一致） */
const PAUSE_DELIVERY_PREP_LOCKED_MSG =
  '21点后无法操作暂停。明日餐品已准备，可配送后暂停'

const pauseDeliveryPrepLocked = computed(() => {
  const p = memberProfileRaw.value
  return Boolean(p && typeof p === 'object' && p.pause_delivery_prep_locked === true)
})

const setupRowTitle = computed(() => {
  if (!needsMemberSetupPage.value) return ''
  const w = wxProfile.value?.nickName?.trim()
  if (w && w !== WX_DEFAULT_NICK) return w
  const un = userName.value?.trim()
  if (un && un !== MEMBER_STUB_NAME) return un
  const p = String(memberPhone.value || '').trim()
  if (p) return p
  return '点我：完善配送信息'
})

const displayNick = computed(() => {
  const w = wxProfile.value?.nickName?.trim()
  if (w && w !== WX_DEFAULT_NICK) return w
  return profileName.value
})

const avatarChar = computed(() => {
  const nick = wxProfile.value?.nickName?.trim()
  if (nick && nick !== WX_DEFAULT_NICK) {
    const ch = nick[0]
    return /[\u4e00-\u9fa5]/.test(ch) ? ch : (nick[0] || 'O').toUpperCase()
  }
  const n = profileName.value
  if (!n) return '员'
  const ch = n[0]
  return /[\u4e00-\u9fa5]/.test(ch) ? ch : 'O'
})

function syncNickDraftFromProfile() {
  const n = wxProfile.value?.nickName?.trim()
  wxNickDraft.value = n && n !== WX_DEFAULT_NICK ? n : ''
}

function wxProfileStorageKey() {
  const phone = memberPhone.value || uni.getStorageSync('memberPhone') || ''
  return phone ? `${WX_PROFILE_PREFIX}:${phone}` : WX_PROFILE_PREFIX
}

function loadWxProfileFromStorage() {
  if (!isLoggedIn.value) {
    wxProfile.value = null
    return
  }
  const key = wxProfileStorageKey()
  try {
    let raw = uni.getStorageSync(key)
    if (
      !raw &&
      typeof localStorage !== 'undefined' &&
      typeof localStorage.getItem === 'function'
    ) {
      const s = localStorage.getItem(key)
      raw = s ? JSON.parse(s) : null
    }
    if (!raw) {
      wxProfile.value = null
      wxNickDraft.value = ''
      return
    }
    wxProfile.value = typeof raw === 'string' ? JSON.parse(raw) : raw
    syncNickDraftFromProfile()
  } catch {
    wxProfile.value = null
    wxNickDraft.value = ''
  }
}

function persistWxProfile(p) {
  const key = wxProfileStorageKey()
  const payload = { nickName: p.nickName || '', avatarUrl: p.avatarUrl || '' }
  uni.setStorageSync(key, payload)
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, JSON.stringify(payload))
    }
  } catch {
    /* 小程序无 localStorage 时忽略 */
  }
}

/**
 * 将会员微信昵称/头像同步到服务端 members.wechat_name、avatar_url
 * @param {{ showErrorToast?: boolean }} [options]
 */
async function pushWechatProfileToServer(partial, options = {}) {
  const { showErrorToast = true } = options
  if (!getMemberToken()) return
  const body = {}
  if (partial.wechat_name !== undefined) body.wechat_name = partial.wechat_name
  if (partial.avatar_url !== undefined) body.avatar_url = partial.avatar_url
  if (Object.keys(body).length === 0) return
  try {
    await request('/api/user/profile', { method: 'PATCH', data: body })
  } catch (err) {
    console.warn('pushWechatProfileToServer', err)
    if (showErrorToast) {
      uni.showToast({ title: err?.message || '资料同步失败', icon: 'none' })
      return
    }
    throw err
  }
}

async function onChooseAvatar(e) {
  const localPath = e.detail?.avatarUrl
  if (!localPath) return
  uni.showLoading({ title: '上传头像…', mask: true })
  try {
    const permanentUrl = await uploadMemberAvatarFile(localPath)
    const nick = String(wxNickDraft.value || '').trim()
    const prev = wxProfile.value || { nickName: '', avatarUrl: '' }
    let mergedNick = nick && nick !== WX_DEFAULT_NICK ? nick : ''
    if (!mergedNick && prev.nickName && prev.nickName !== WX_DEFAULT_NICK) {
      mergedNick = prev.nickName.trim()
    }
    if (!mergedNick && userName.value?.trim() && userName.value.trim() !== MEMBER_STUB_NAME) {
      mergedNick = userName.value.trim()
    }
    const p = { nickName: mergedNick, avatarUrl: permanentUrl }
    wxProfile.value = p
    persistWxProfile(p)
    const syncPayload = { avatar_url: permanentUrl }
    if (mergedNick && mergedNick !== WX_DEFAULT_NICK) syncPayload.wechat_name = mergedNick
    await pushWechatProfileToServer(syncPayload, { showErrorToast: false })
    if (memberProfileRaw.value && typeof memberProfileRaw.value === 'object') {
      memberProfileRaw.value = { ...memberProfileRaw.value, avatar_url: permanentUrl }
    }
    void refreshMember()
    if (!mergedNick || mergedNick === WX_DEFAULT_NICK) {
      uni.showToast({ title: '头像已上传，请完善昵称', icon: 'none', duration: 2200 })
    } else {
      uni.showToast({ title: '头像已更新', icon: 'success' })
    }
  } catch (err) {
    uni.showToast({
      title: err?.message || '头像上传失败',
      icon: 'none',
      duration: 2800,
    })
  } finally {
    uni.hideLoading()
  }
}

/** 会员资料区展示手机号（中间四位脱敏，如 132****6633） */
function formatDisplayPhone(raw) {
  const digits = String(raw || '').replace(/\D/g, '')
  if (!digits) return '未绑定手机'
  if (digits.length === 11) return `${digits.slice(0, 3)}****${digits.slice(7)}`
  if (digits.length < 7) return raw && String(raw).trim() ? String(raw).trim() : '未绑定手机'
  return `${digits.slice(0, 3)}****${digits.slice(-4)}`
}

const displayPhone = computed(() => {
  if (!isLoggedIn.value) return ''
  return formatDisplayPhone(memberPhone.value)
})

/** 计划卡片：未登录展示 0，已登录用动效后的余额（含体验加餐次） */
const planCardRemainingMeals = computed(() => {
  if (!isLoggedIn.value) return 0
  return displayBalance.value
})

const planCardStatusAlert = computed(
  () => isLoggedIn.value && needsMemberSetupPage.value,
)

const planCardAddressLine = computed(() => {
  if (!isLoggedIn.value) return ''
  return todayDeliveryAddressLine.value
})

function onMineHeroTap() {
  if (needsMemberSetupPage.value) goMemberSetup()
}

function goMembershipCardPack() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先手机号登录', icon: 'none' })
    return
  }
  uni.navigateTo({
    url: '/packageUser/pages/membershipCardList/membershipCardList',
  })
}

function goMyCoupons() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/packageUser/pages/myCoupons/myCoupons' })
}

function goDouyinRedeem() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/packageUser/pages/douyinRedeem/douyinRedeem' })
}

function onNickInput(e) {
  wxNickDraft.value = e.detail?.value ?? ''
}

function closeNickEditor() {
  showNickEditor.value = false
  nickInputFocus.value = false
}

function onNickWrapTap() {
  if (needsMemberSetupPage.value) {
    goMemberSetup()
    return
  }
  openNickEditor()
}

function openNickEditor() {
  if (!isLoggedIn.value) return
  syncNickDraftFromProfile()
  const draft = String(wxNickDraft.value || '').trim()
  const phoneLike = /^\d{7,}$/.test(draft)
  if (!draft || draft === WX_DEFAULT_NICK || draft === MEMBER_STUB_NAME || phoneLike) {
    wxNickDraft.value = ''
  }
  showNickEditor.value = true
  nickInputFocus.value = false
  nextTick(() => {
    nickInputFocus.value = true
  })
}

async function confirmNickEdit() {
  const nick = String(wxNickDraft.value || '').trim()
  if (!nick || nick === WX_DEFAULT_NICK) {
    uni.showToast({ title: '请填写或选用微信昵称', icon: 'none' })
    return
  }
  const prev = wxProfile.value || { nickName: '', avatarUrl: '' }
  const p = { ...prev, nickName: nick }
  wxProfile.value = p
  persistWxProfile(p)
  const syncPayload = { wechat_name: nick }
  if (p.avatarUrl?.trim()) syncPayload.avatar_url = p.avatarUrl.trim()
  closeNickEditor()
  try {
    await pushWechatProfileToServer(syncPayload, { showErrorToast: true })
    if (memberProfileRaw.value && typeof memberProfileRaw.value === 'object') {
      memberProfileRaw.value = { ...memberProfileRaw.value, wechat_name: nick }
    }
    if (!p.avatarUrl?.trim()) {
      uni.showToast({ title: '昵称已更新，可点头像上传照片', icon: 'none', duration: 2400 })
    } else {
      uni.showToast({ title: '昵称已更新', icon: 'success' })
    }
  } catch {
    /* pushWechatProfileToServer 已 toast */
  }
}

/** 与后台一致：区间、仅明日请假；含「已提交未来区间」；文案展示具体日期 */
const memberDeliveryStatus = computed(() => {
  if (!isLoggedIn.value) return '尚未开启计划'
  if (needsMemberSetupPage.value) return ''
  if (
    isOnLeaveTodayShanghai(leaveRange.value) ||
    isTomorrowLeaveActive(isLeavedTomorrow.value, tomorrowLeaveTargetYmd.value) ||
    isLeaveRangeActiveOrFuture(leaveRange.value)
  ) {
    if (isOnLeaveTodayShanghai(leaveRange.value)) {
      const lr = leaveRange.value
      const sRaw = lr?.start != null ? String(lr.start).slice(0, 10) : ''
      const eRaw = lr?.end != null ? String(lr.end).slice(0, 10) : ''
      const sm = ymdToCnMd(sRaw)
      const em = ymdToCnMd(eRaw)
      if (sm && em) {
        if (sRaw === eRaw) return `${sm}请假`
        return `${sm}-${em}请假`
      }
      return '请假中'
    }
    if (isLeaveRangeActiveOrFuture(leaveRange.value) && !isOnLeaveTodayShanghai(leaveRange.value)) {
      const lr = leaveRange.value
      const sRaw = lr?.start != null ? String(lr.start).slice(0, 10) : ''
      const eRaw = lr?.end != null ? String(lr.end).slice(0, 10) : ''
      const sm = ymdToCnMd(sRaw)
      const em = ymdToCnMd(eRaw)
      if (sm && em) {
        if (sRaw === eRaw) return `${sm}起请假`
        return `${sm}-${em}请假`
      }
      return '已预约请假'
    }
    if (isTomorrowLeaveActive(isLeavedTomorrow.value, tomorrowLeaveTargetYmd.value)) {
      return '明日请假中'
    }
    return '请假中'
  }
  if (isDeliveryPausedWithBalance(memberProfileRaw.value)) return '暂停配送'
  if (showMemberCardModule.value) return ''
  const p = memberProfileRaw.value
  const today = ymdTodayShanghai()
  if (isMemberInActiveDelivery(p, today)) return '正常配送中'
  if (isMemberDeliveryScheduledFuture(p, today)) {
    const startMd = ymdToCnMd(p?.delivery_start_date)
    return startMd ? `${startMd}起配送` : '待起送'
  }
  return ''
})

const planTypeMemberLabel = computed(() => {
  if (!isLoggedIn.value || needsMemberSetupPage.value) return ''
  const p = String(planType.value || '').trim()
  return p ? `${p}会员` : ''
})

const cardFooter = computed(() => {
  if (!isLoggedIn.value) return '自律，从今天第一顿 OK 饭开始 👌'
  return `已陪伴您自律生活：${displayCompanionDays.value} 天 👌`
})

const todayDeliveryAddressLine = computed(() => {
  const line = defaultAddrLine.value?.trim()
  if (line) return `默认配送地址：${line}`
  const p = memberProfileRaw.value
  const profileAddr = p?.address != null ? String(p.address).trim() : ''
  if (profileAddr) return `默认配送地址：${profileAddr}`
  if (p?.store_pickup === true) return '履约方式：门店自提'
  return '默认配送地址：未设置'
})

function mergeMemberApiProfile(data) {
  memberProfileRaw.value = data && typeof data === 'object' ? data : null
  if (!data || typeof data !== 'object') return
  if (data.id != null) {
    try {
      uni.setStorageSync('memberId', String(data.id))
    } catch {
      /* ignore */
    }
  }
  userName.value = data.name != null ? String(data.name) : ''
  serverBalance.value = Math.max(0, Math.floor(Number(data.balance) || 0))
  planType.value = data.plan_type != null ? String(data.plan_type) : ''
  leaveRange.value =
    data.leave_range && typeof data.leave_range === 'object' ? data.leave_range : null
  isLeavedTomorrow.value = data.is_leaved_tomorrow === true
  tomorrowLeaveTargetYmd.value = ymdFromApi(data.tomorrow_leave_target_date)
  isActive.value = !!data.is_active
  createdAt.value = data.created_at != null ? String(data.created_at) : ''
  {
    const u = Math.floor(Number(data.daily_meal_units) || 0)
    dailyMealUnits.value = u >= 1 && u <= 50 ? u : 1
  }

  /** 服务端档案优先：头像 +昵称（wechat_name，缺省用非占位 name）合并进本地展示缓存 */
  const av = data.avatar_url != null ? String(data.avatar_url).trim() : ''
  const wnRaw = data.wechat_name != null ? String(data.wechat_name).trim() : ''
  const wn = wnRaw && wnRaw !== WX_DEFAULT_NICK ? wnRaw : ''
  const nm = data.name != null ? String(data.name).trim() : ''
  const nameOk = nm && nm !== MEMBER_STUB_NAME ? nm : ''
  const nickFromServer = wn || nameOk
  if (av || nickFromServer) {
    const prev = wxProfile.value || {}
    const prevNick =
      prev.nickName && String(prev.nickName).trim() && prev.nickName !== WX_DEFAULT_NICK
        ? String(prev.nickName).trim()
        : ''
    const prevUrl = prev.avatarUrl != null ? String(prev.avatarUrl).trim() : ''
    const merged = {
      nickName: nickFromServer || prevNick,
      avatarUrl: av || prevUrl,
    }
    if (merged.nickName || merged.avatarUrl) {
      wxProfile.value = merged
      persistWxProfile(merged)
      syncNickDraftFromProfile()
    }
  }
}

/** @param {{ prefetched?: object | null, skipAddress?: boolean, skipProfileCompleteRedirect?: boolean }} [options] 登录流程已请求过 GET /api/user/me 时可传入 prefetched */
async function refreshMember(options = {}) {
  const seq = ++refreshMemberSeq
  const { prefetched, skipAddress = false, skipProfileCompleteRedirect = false } = options
  const token = getMemberToken()
  const phone = uni.getStorageSync('memberPhone') || ''
  isLoggedIn.value = !!token
  memberPhone.value = phone

  if (!isLoggedIn.value) {
    if (seq !== refreshMemberSeq) return
    memberProfileRaw.value = null
    serverBalance.value = 0
    userName.value = ''
    planType.value = ''
    leaveRange.value = null
    isLeavedTomorrow.value = false
    tomorrowLeaveTargetYmd.value = ''
    isActive.value = false
    createdAt.value = ''
    dailyMealUnits.value = 1
    wxProfile.value = null
    wxNickDraft.value = ''
    defaultAddrLine.value = ''
    syncPlanCardDisplay()
    return
  }

  loadWxProfileFromStorage()
  const pre = prefetched
  if (pre && typeof pre === 'object') {
    if (seq !== refreshMemberSeq) return
    mergeMemberApiProfile(pre)
    const sp = pre.phone != null ? String(pre.phone).trim() : ''
    if (sp) {
      memberPhone.value = sp
      try {
        uni.setStorageSync('memberPhone', sp)
      } catch {
        /* ignore */
      }
    }
  } else {
    try {
      const data = await request('/api/user/me', { method: 'GET' })
      if (seq !== refreshMemberSeq) return
      mergeMemberApiProfile(data)
      const sp = data?.phone != null ? String(data.phone).trim() : ''
      if (sp) {
        memberPhone.value = sp
        try {
          uni.setStorageSync('memberPhone', sp)
        } catch {
          /* ignore */
        }
      }
    } catch (e) {
      if (seq !== refreshMemberSeq) return
      if (isUserMeNotFoundError(e)) {
        clearMemberSession()
      }
      memberProfileRaw.value = null
      serverBalance.value = 0
      userName.value = ''
      planType.value = ''
      leaveRange.value = null
      isLeavedTomorrow.value = false
      tomorrowLeaveTargetYmd.value = ''
      isActive.value = false
      createdAt.value = ''
      dailyMealUnits.value = 1
      const t = getMemberToken()
      isLoggedIn.value = !!t
      memberPhone.value = uni.getStorageSync('memberPhone') || ''
      if (!isLoggedIn.value) {
        wxProfile.value = null
        wxNickDraft.value = ''
        defaultAddrLine.value = ''
      }
    }
  }

  if (seq !== refreshMemberSeq) return
  if (getMemberToken() && !skipAddress) {
    await syncDefaultAddressForCard(seq)
  }

  if (seq !== refreshMemberSeq) return
  syncPlanCardDisplay({ animate: true })
  if (!skipProfileCompleteRedirect) {
    maybeRedirectToProfileComplete()
  }
}

/** 已登录但昵称未完善时，引导至设置昵称页 */
function maybeRedirectToProfileComplete() {
  if (!isLoggedIn.value || profileCompleteNavLock) return
  if (!shouldCompleteMemberProfile(memberProfileRaw.value)) return
  profileCompleteNavLock = true
  uni.navigateTo({
    url: '/packageUser/pages/memberProfileComplete/memberProfileComplete?from=required',
    fail: (e) => {
      console.error('navigateTo memberProfileComplete', e)
      profileCompleteNavLock = false
    },
    complete: () => {
      setTimeout(() => {
        profileCompleteNavLock = false
      }, 600)
    },
  })
}

function goMemberProfileComplete(from) {
  const q = from ? `?from=${encodeURIComponent(from)}` : ''
  uni.navigateTo({
    url: `/packageUser/pages/memberProfileComplete/memberProfileComplete${q}`,
    fail: (e) => {
      console.error('navigateTo memberProfileComplete', e)
      uni.showToast({ title: '无法打开页面，请重试', icon: 'none' })
    },
  })
}

/** 下拉刷新：强制拉取会员档案与默认地址 */
async function onMineRefresherRefresh() {
  refresherTriggered.value = true
  try {
    await refreshMember()
  } finally {
    refresherTriggered.value = false
  }
}

onShow(() => {
  if (reLaunchIfCourierModePreferred()) return
  syncCustomTabBar()
  syncTabLayout()
  try {
    const pending = uni.getStorageSync('okfood_pending_mine_toast')
    if (pending) {
      uni.removeStorageSync('okfood_pending_mine_toast')
      setTimeout(() => {
        uni.showToast({ title: String(pending), icon: 'none', duration: 3200 })
      }, 120)
    }
  } catch {
    /* ignore */
  }
  tryOpenOrdersFromCheckoutFlag()
  consumeMinePageNeedsRefresh()
  void refreshMember()
})

onMounted(() => {
  syncTabLayout()
})

async function onWxGetPhoneNumber(e) {
  const detail = e?.detail ?? {}
  const errMsg = String(detail.errMsg || '')
  if (errMsg.includes('deny') || errMsg.includes('cancel')) {
    uni.showToast({ title: '需要授权手机号才能登录', icon: 'none' })
    return
  }
  if (!hasWxPhoneAuthDetail(detail)) {
    uni.showToast({
      title: errMsg || '未收到微信授权数据，请重试',
      icon: 'none',
    })
    return
  }
  uni.showLoading({ title: '登录中', mask: true })
  try {
    const { profile } = await wxMiniMemberLoginAndStore(detail)
    await refreshMember({ prefetched: profile, skipProfileCompleteRedirect: true })
    uni.hideLoading()
    const snapshot = memberProfileRaw.value ?? profile
    if (shouldCompleteMemberProfile(snapshot)) {
      setTimeout(() => {
        goMemberProfileComplete('login')
      }, 120)
      return
    }
    const needSetup = shouldOpenMemberSetup(snapshot)
    if (needSetup) {
      const paidPending = snapshot?.paid_card_awaiting_setup === true
      const fromQ = paidPending ? 'from=pay' : 'from=login'
      setTimeout(() => {
        uni.navigateTo({
          url: `/packageUser/pages/memberSetup/memberSetup?${fromQ}`,
          fail: (e) => {
            console.error('navigateTo memberSetup', e)
            uni.showToast({ title: '无法打开页面，请重试', icon: 'none' })
          },
        })
      }, 120)
      return
    }
    // 与 showLoading 同时调 showToast 易触发基础库 timeout；先关遮罩再提示
    setTimeout(() => {
      uni.showToast({ title: '登录成功', icon: 'success' })
    }, 50)
  } catch (err) {
    uni.hideLoading()
    setTimeout(() => {
      uni.showToast({
        title: err?.message || '登录失败',
        icon: 'none',
        duration: 2800,
      })
    }, 50)
  }
}

function handlePurchase(price, meals) {
  if (!isLoggedIn.value) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  showOkAlert({
    title: '套餐购买',
    content: `支付金额：¥${price}\n将为您增加 ${meals} 次餐次（演示：确认后本地累加，正式环境对接支付与后端）`,
    success: (res) => {
      if (!res.confirm) return
      addDemoCredits(meals)
      const nextTotal = serverBalance.value + getDemoCredits()
      animateNumberTo(displayBalance, nextTotal)
    },
  })
}

function goCourier() {
  if (getCourierToken()) {
    setAppUserMode('courier')
    uni.reLaunch({ url: '/pages/courier/home' })
    return
  }
  uni.navigateTo({ url: '/pages/courier/login' })
}

function goLeave() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (!guardMemberDeliverySelfService(memberProfileRaw.value)) return
  uni.navigateTo({ url: '/packageUser/pages/leave/leave' })
}
function goAddress() {
  uni.navigateTo({ url: '/packageUser/pages/address/list' })
}

function goSingleOrders() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/packageOrder/pages/singleOrderList/singleOrderList' })
}

function goMyOrders() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.switchTab({ url: '/pages/orders/index' })
}

const STORAGE_OPEN_MY_ORDERS = 'okfood_open_my_orders_after_checkout'

function tryOpenOrdersFromCheckoutFlag() {
  try {
    const v = uni.getStorageSync(STORAGE_OPEN_MY_ORDERS)
    if (v !== '1' && v !== 1 && v !== true) return
    uni.removeStorageSync(STORAGE_OPEN_MY_ORDERS)
    setTimeout(() => {
      if (!getMemberToken()) return
      uni.switchTab({
        url: '/pages/orders/index',
        fail: (e) => {
          console.error('switchTab orders', e)
        },
      })
    }, 80)
  } catch {
    /* ignore */
  }
}

function goDailyMealUnits() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (!guardMemberDeliverySelfService(memberProfileRaw.value)) return
  uni.navigateTo({ url: '/packageUser/pages/dailyMealUnits/dailyMealUnits' })
}

function goMemberSetup() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  let from = ''
  if (needsMemberSetupPage.value) {
    const paidPending =
      memberProfileRaw.value &&
      typeof memberProfileRaw.value === 'object' &&
      memberProfileRaw.value.paid_card_awaiting_setup === true
    if (paidPending) from = 'pay'
  } else {
    // 资料已完善：齿轮入口进入修改配送/自提（勿被「配送信息已完善」拦截退回）
    from = 'edit'
  }
  const q = from ? `?from=${encodeURIComponent(from)}` : ''
  uni.navigateTo({
    url: `/packageUser/pages/memberSetup/memberSetup${q}`,
    fail: (e) => {
      console.error('navigateTo memberSetup', e)
      uni.showToast({ title: '无法打开页面，请重试', icon: 'none' })
    },
  })
}

function goResumeDelivery() {
  uni.navigateTo({
    url: '/packageUser/pages/memberSetup/memberSetup?from=resume',
    fail: (e) => {
      console.error('navigateTo memberSetup resume', e)
      uni.showToast({ title: '无法打开资料页，请重试', icon: 'none' })
    },
  })
}

function onPauseDeliveryTap() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (!guardMemberDeliverySelfService(memberProfileRaw.value)) return
  if (pauseDeliveryPrepLocked.value) {
    uni.showModal({
      title: '暂无法暂停',
      content: PAUSE_DELIVERY_PREP_LOCKED_MSG,
      showCancel: false,
      confirmText: '知道了',
    })
    return
  }
  // 真机 Tab 页：自定义 OkAlert Host 在部分机型上无法即时挂载，此处用原生弹窗保证可点即弹
  uni.showModal({
    title: '暂停配送',
    content:
      '确认后暂停会员卡配送（剩余餐次保留）。恢复时需重新选择开始的业务日期。是否暂停？',
    confirmText: '暂停配送',
    cancelText: '取消',
    confirmColor: '#0e5a44',
    success: async (res) => {
      if (!res.confirm) return
      uni.showLoading({ title: '提交中', mask: true })
      try {
        await request('/api/user/profile', {
          method: 'PATCH',
          data: { delivery_deferred: true },
        })
        markMinePageNeedsRefresh()
        await refreshMember()
        uni.showToast({ title: '已暂停配送', icon: 'success' })
      } catch (err) {
        uni.showToast({
          title: err?.message || '操作失败',
          icon: 'none',
          duration: 2800,
        })
      } finally {
        uni.hideLoading()
      }
    },
  })
}
</script>

<style lang="scss" scoped>
.page-shell {
  height: 100%;
  position: relative;
}

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
  background: $ok-slate-50;
}

.profile-container {
  padding: 28rpx 32rpx 40rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
}

.mine-hero {
  margin-bottom: 28rpx;
  padding: 8rpx 0 24rpx;
}

.mine-hero--tap {
  opacity: 0.98;
}

.mine-hero--guest {
  padding: 20rpx 0 36rpx;
  margin-bottom: 8rpx;
}

.hero-guest-inner {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 28rpx;
}

.hero-guest-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.guest-hint {
  font-size: 24rpx;
  color: $ok-slate-500;
  font-weight: 600;
  line-height: 1.45;
}

.hero-avatar-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  margin-bottom: 20rpx;
}

.hero-avatar-wrap {
  flex-shrink: 0;
}

.hero-avatar-btn {
  padding: 0;
  margin: 0;
  background: transparent;
  border: none;
  line-height: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: top;
  border-radius: 0;
  min-width: 0;
  width: auto;
  height: auto;
}

.hero-avatar-btn::after {
  border: none;
  border-radius: 0;
  padding: 0;
  margin: 0;
}

.hero-avatar-btn--static {
  display: inline-block;
  vertical-align: top;
}

.hero-avatar-row .avatar-ring {
  border-width: 4rpx;
  box-shadow: 0 10rpx 28rpx rgba(14, 90, 68, 0.14);
}

.avatar-ring {
  width: 148rpx;
  height: 148rpx;
  border-radius: 50%;
  background: linear-gradient(145deg, $ok-forest-green 0%, $ok-forest-green-dark 100%);
  border: 8rpx solid #fff;
  box-shadow: 0 16rpx 40rpx rgba(14, 90, 68, 0.22);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-ring--guest {
  width: 120rpx;
  height: 120rpx;
  background: $ok-slate-300;
  border-color: #fff;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.08);
}

.avatar-img {
  width: 100%;
  height: 100%;
  display: block;
}

.avatar-fallback {
  font-size: 56rpx;
  font-weight: 950;
  color: #fff;
}

.avatar-fallback-sm {
  font-size: 48rpx;
  font-weight: 950;
  color: #fff;
}

.hero-nick-wrap {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  margin-bottom: 12rpx;
  padding: 4rpx 12rpx;
}

.hero-nick-wrap--action {
  opacity: 0.98;
}

.hero-nick {
  display: block;
  text-align: center;
  font-size: 40rpx;
  font-weight: 950;
  color: #0f172a;
}

.hero-nick--editable {
  color: #0f172a;
}

.hero-nick--action {
  color: $ok-forest-green;
}

.hero-nick-edit {
  font-size: 26rpx;
  color: $ok-slate-400;
  line-height: 1;
}

.nick-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48rpx;
  box-sizing: border-box;
}

.nick-sheet {
  width: 100%;
  max-width: 620rpx;
  background: #fff;
  border-radius: 28rpx;
  padding: 40rpx 36rpx 32rpx;
  box-shadow: 0 24rpx 64rpx rgba(15, 23, 42, 0.18);
}

.nick-sheet-title {
  display: block;
  text-align: center;
  font-size: 34rpx;
  font-weight: 900;
  color: #0f172a;
  margin-bottom: 12rpx;
}

.nick-sheet-hint {
  display: block;
  text-align: center;
  font-size: 24rpx;
  font-weight: 600;
  color: $ok-slate-500;
  margin-bottom: 28rpx;
  line-height: 1.45;
}

.nick-sheet-input {
  width: 100%;
  box-sizing: border-box;
  height: 88rpx;
  padding: 0 28rpx;
  border-radius: 20rpx;
  background: $ok-slate-50;
  border: 2rpx solid $ok-slate-100;
  font-size: 30rpx;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 32rpx;
}

.nick-sheet-ph {
  color: $ok-slate-400;
  font-weight: 600;
}

.nick-sheet-actions {
  display: flex;
  flex-direction: row;
  gap: 20rpx;
}

.nick-sheet-btn {
  flex: 1;
  margin: 0;
  padding: 0;
  height: 84rpx;
  line-height: 84rpx;
  border-radius: 999rpx;
  font-size: 30rpx;
  font-weight: 800;
  border: none;
}

.nick-sheet-btn::after {
  border: none;
}

.nick-sheet-btn--ghost {
  background: $ok-slate-100;
  color: $ok-slate-600;
}

.nick-sheet-btn--primary {
  background: $ok-forest-green;
  color: #fff;
}

.hero-phone-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
}

.hero-phone {
  font-size: 26rpx;
  font-weight: 700;
  color: $ok-slate-600;
}

.hero-gear {
  padding: 6rpx 10rpx;
  border-radius: 12rpx;
  background: rgba(14, 90, 68, 0.08);
}

.hero-gear-icon {
  font-size: 28rpx;
  color: $ok-forest-green;
  line-height: 1;
}

.hero-setup-hint {
  display: block;
  text-align: center;
  font-size: 24rpx;
  font-weight: 700;
  color: $ok-forest-green;
  margin-top: 16rpx;
}

.section-cap {
  display: block;
  font-size: 24rpx;
  font-weight: 800;
  color: $ok-slate-500;
  margin-bottom: 16rpx;
  padding-left: 6rpx;
}

.section-cap--sp {
  margin-top: 12rpx;
}

.menu-card {
  background: #fff;
  border-radius: 28rpx;
  padding: 28rpx 20rpx 20rpx;
  margin-bottom: 24rpx;
  border: 2rpx solid $ok-slate-100;
  box-shadow: 0 8rpx 28rpx rgba(15, 23, 42, 0.05);
}

.menu-grid {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
}

.menu-grid--3 .menu-cell {
  width: 33.333%;
}

.menu-cell {
  width: 33.333%;
  box-sizing: border-box;
  padding: 12rpx 8rpx 20rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
}

.menu-ico-wrap {
  width: 96rpx;
  height: 96rpx;
  border-radius: 22rpx;
  background: rgba(14, 90, 68, 0.08);
  border: 2rpx solid rgba(167, 243, 208, 0.35);
  box-shadow: 0 4rpx 14rpx rgba(15, 23, 42, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-ico-img {
  width: 44rpx;
  height: 44rpx;
}

.menu-cap {
  font-size: 22rpx;
  font-weight: 800;
  color: #334155;
  text-align: center;
  line-height: 1.35;
  padding: 0 4rpx;
}

.menu-extra {
  margin-top: 12rpx;
  padding: 20rpx 24rpx;
  background: $ok-slate-50;
  border-radius: 20rpx;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.menu-extra-txt {
  font-size: 26rpx;
  font-weight: 800;
  color: #475569;
}

.menu-extra-arr {
  font-size: 36rpx;
  color: #cbd5e1;
}

/* 微信授权手机号 */
.wx-login-btn {
  margin: 0;
  padding: 26rpx 40rpx;
  width: 100%;
  max-width: 420rpx;
  box-sizing: border-box;
  font-size: 32rpx;
  font-weight: 800;
  color: #fff;
  background: $ok-forest-green;
  border: none;
  border-radius: 999rpx;
  line-height: 1.35;
  box-shadow: 0 8rpx 22rpx rgba(14, 90, 68, 0.3);
}

.wx-login-btn::after {
  border: none;
}

.wx-login-btn--hover {
  opacity: 0.9;
}

/* 页面底部版本号（低调展示） */
.page-version {
  display: block;
  margin-top: 40rpx;
  text-align: center;
  font-size: 18rpx;
  font-weight: 500;
  color: #c8c8c8;
  letter-spacing: 0.5rpx;
}
</style>
