<template>
  <view class="page" :style="pageStyle">
    <OkNavbar show-brand />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="profile-container">
        <button
          v-if="!isLoggedIn"
          class="user-header user-header--wx"
          open-type="getPhoneNumber"
          @getphonenumber="onWxGetPhoneNumber"
        >
          <view :class="['avatar-box', 'avatar-box--guest']">
            <text class="avatar-txt avatar-txt--guest">?</text>
          </view>
          <view class="user-name-box">
            <text class="nick-name nick-name--action">微信一键登录</text>
            <text class="level-text">授权手机号后与会员档案、餐次同步</text>
          </view>
        </button>
        <view v-else-if="needsMemberSetupPage" class="user-header user-header--setup" @click="goMemberSetup">
          <button
            class="avatar-btn"
            open-type="chooseAvatar"
            @chooseavatar="onChooseAvatar"
            @tap.stop
          >
            <view class="avatar-box avatar-box--setup">
              <image
                v-if="setupRowAvatarUrl"
                class="avatar-img"
                :src="setupRowAvatarUrl"
                mode="aspectFill"
              />
              <text v-else class="avatar-txt">填</text>
            </view>
          </button>
          <view class="user-name-box user-name-box--flex">
            <text class="nick-name nick-name--action">{{ setupRowTitle }}</text>
            <text class="level-text">{{ setupRowPhoneLine }}</text>
          </view>
          <text class="setup-chevron">›</text>
        </view>
        <view v-else class="user-header">
          <button class="avatar-btn" open-type="chooseAvatar" @chooseavatar="onChooseAvatar">
            <view class="avatar-box">
              <image
                v-if="wxProfile?.avatarUrl"
                class="avatar-img"
                :src="wxProfile.avatarUrl"
                mode="aspectFill"
              />
              <text v-else class="avatar-txt">{{ avatarChar }}</text>
            </view>
          </button>
          <view class="user-name-box user-name-box--flex">
            <text class="nick-name">{{ displayNick }}</text>
            <text v-if="profileSub" class="level-text">{{ profileSub }}</text>
          </view>
        </view>

        <view class="vip-card">
          <view class="vip-card-head">
            <text class="vip-tag">OK 饭 自律计划</text>
            <text v-if="planTypeMemberLabel" class="member-plan-kind">{{ planTypeMemberLabel }}</text>
          </view>
          <view class="balance-line">
            <text class="num">{{ displayBalance }}</text>
            <text class="unit">剩余餐次</text>
            <text class="type-label">{{ memberDeliveryStatus }}</text>
          </view>
          <text v-if="isLoggedIn" class="today-delivery-addr">{{ todayDeliveryAddressLine }}</text>
          <text class="footer-info">{{ cardFooter }}</text>
        </view>

        <view v-if="showOpenCardRenewPanel" class="open-card-banner">
          <text class="open-card-banner-title">还未开卡</text>
          <text class="open-card-banner-desc">
            上次支付未完成或尚未开通，可选套餐再次发起微信支付；支付成功后餐次将自动到账。
          </text>
          <view class="subscription-cards open-card-cards">
            <view
              :class="['sub-plan-item', cardPayLoading ? 'sub-plan-item--disabled' : '']"
              @tap="onMineCardPay('周卡')"
            >
              <text class="plan-en">WEEKLY</text>
              <text class="plan-name">6 天自律周卡</text>
              <text class="plan-price"><text class="yen">¥</text>{{ cardPriceWeek }}</text>
            </view>
            <view
              :class="['sub-plan-item', 'highlight', cardPayLoading ? 'sub-plan-item--disabled' : '']"
              @tap="onMineCardPay('月卡')"
            >
              <text class="rec-badge">推荐</text>
              <text class="plan-en">MONTHLY</text>
              <text class="plan-name">24 天全能月卡</text>
              <text class="plan-price"><text class="yen">¥</text>{{ cardPriceMonth }}</text>
            </view>
          </view>
          <view class="open-card-foot" @tap="goMemberSetup">
            <text class="open-card-foot-text">修改昵称、头像或开始配送日期</text>
            <text class="open-card-foot-arrow">›</text>
          </view>
        </view>

        <view class="action-list">
          <view v-if="!isLoggedIn" class="menu-row" @click="goCourier">
            <text class="menu-label">配送员工作台</text>
            <text class="arrow">›</text>
          </view>
          <view class="menu-row" @click="goLeave">
            <text class="menu-label">😴 请假管理</text>
            <text class="arrow">›</text>
          </view>
          <view class="menu-row" @click="goAddress">
            <text class="menu-label">🏠 地址管理</text>
            <text class="arrow">›</text>
          </view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import {
  request,
  getMemberToken,
  getCourierToken,
  setAppUserMode,
  reLaunchIfCourierModePreferred,
  uploadMemberAvatarFile,
} from '@/utils/api.js'
import { wxMiniMemberLoginAndStore, hasWxPhoneAuthDetail } from '@/utils/wxMemberLogin.js'
import {
  shouldOpenMemberSetup,
  isPlaceholderWxProfile,
  MEMBER_STUB_NAME,
  WX_DEFAULT_NICK,
} from '@/utils/memberProfile.js'
import { runMemberCardWechatPay } from '@/utils/memberCardPay.js'
import { getTabPageLayoutStyles } from '@/utils/tabPageLayout.js'
import { syncCustomTabBar } from '@/utils/customTabBar.js'
import {
  normalizeAddressList,
  addressListRow,
  sortAddressesDefaultFirst,
  isAddressItemDefault,
} from '@/utils/addressApi.js'

const pageStyle = ref({})
const scrollStyle = ref({})

function syncTabLayout() {
  const { pageStyle: p, scrollStyle: s } = getTabPageLayoutStyles()
  pageStyle.value = p
  scrollStyle.value = s
}

const DEMO_MEAL_KEY = 'okfood_demo_meal_credits'
/** 微信头像昵称（按手机号分 key，等同 H5 localStorage 分用户存储） */
const WX_PROFILE_PREFIX = 'okfood_wx_profile'
const isLoggedIn = ref(false)
const memberPhone = ref('')
const wxProfile = ref(null)
/** 昵称输入（type=nickname 可走微信键盘同步） */
const wxNickDraft = ref('')
const serverBalance = ref(0)
const userName = ref('')
const planType = ref('')
const leaveRange = ref(null)
const isActive = ref(false)
const createdAt = ref('')
/** 与界面同步的剩余餐次（含滚动动画） */
const displayBalance = ref(0)
/** 默认配送地址展示行（area + detail，与地址列表一致） */
const defaultAddrLine = ref('')
let fetchDefaultAddrSeq = 0

const cardPayLoading = ref(false)
const cardPriceWeek = ref('168')
const cardPriceMonth = ref('669')

async function fetchDefaultAddressForCard() {
  const seq = ++fetchDefaultAddrSeq
  if (!getMemberToken()) {
    defaultAddrLine.value = ''
    return
  }
  try {
    const data = await request('/api/user/me/addresses', { method: 'GET' })
    if (seq !== fetchDefaultAddrSeq) return
    const sorted = sortAddressesDefaultFirst(normalizeAddressList(data))
    const defItem = sorted.find((item) => isAddressItemDefault(item))
    const row = defItem ? addressListRow(defItem, 0) : null
    defaultAddrLine.value = row?.line?.trim() || ''
  } catch {
    if (seq !== fetchDefaultAddrSeq) return
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

/** 数字递增至 target（购买成功等场景） */
function animateBalanceTo(target) {
  const to = Math.max(0, Math.floor(target))
  const from = displayBalance.value
  if (from === to) return
  const duration = 720
  const t0 = Date.now()
  const step = () => {
    const elapsed = Date.now() - t0
    const t = Math.min(1, elapsed / duration)
    const eased = 1 - (1 - t) ** 3
    displayBalance.value = Math.round(from + (to - from) * eased)
    if (t < 1) nextFrame(step)
    else displayBalance.value = to
  }
  nextFrame(step)
}

function syncDisplayNoAnim() {
  if (!isLoggedIn.value) {
    displayBalance.value = 0
    return
  }
  const total = serverBalance.value + getDemoCredits()
  displayBalance.value = Math.max(0, total)
}

const profileName = computed(() => {
  if (userName.value?.trim()) return userName.value.trim()
  const p = memberPhone.value
  if (p && p.length === 11) return `${p.slice(0, 3)}****${p.slice(-4)}`
  return '会员'
})

/** 服务端档案缺项时引导至完善资料页 */
const memberProfileRaw = ref(null)

const needsMemberSetupPage = computed(() => {
  if (!isLoggedIn.value) return false
  return shouldOpenMemberSetup(memberProfileRaw.value)
})

/** 资料已具备开卡条件：可用昵称 + 起送日（与完善资料页支付前一致） */
const profileReadyForCardPay = computed(() => {
  const p = memberProfileRaw.value
  if (!p || typeof p !== 'object') return false
  const nm = (p.name != null ? String(p.name) : '').trim()
  const stub = nm === MEMBER_STUB_NAME || nm === ''
  const wn = (p.wechat_name != null ? String(p.wechat_name) : '').trim()
  const wxOk = wn !== '' && wn !== WX_DEFAULT_NICK
  const hasUsableName = wxOk || (!stub && nm !== '')
  const ds = p.delivery_start_date != null ? String(p.delivery_start_date).trim() : ''
  const hasDelivery = ds.length >= 10
  return hasUsableName && hasDelivery
})

const deliveryStartYmdFromProfile = computed(() => {
  const p = memberProfileRaw.value
  if (!p || typeof p !== 'object') return ''
  const ds = p.delivery_start_date != null ? String(p.delivery_start_date).trim() : ''
  return ds.length >= 10 ? ds.slice(0, 10) : ''
})

/** 已登录、服务端剩余 0、且资料已齐：在个人中心直接续办开卡支付 */
const showOpenCardRenewPanel = computed(() => {
  if (!isLoggedIn.value) return false
  if (serverBalance.value > 0) return false
  return profileReadyForCardPay.value
})

function isHttpAvatarUrl(u) {
  const s = String(u || '').trim()
  return /^https?:\/\//i.test(s)
}

/** 待完善资料横幅：优先展示已同步的 http(s) 头像 */
const setupRowAvatarUrl = computed(() => {
  if (!needsMemberSetupPage.value) return ''
  const w = wxProfile.value?.avatarUrl
  if (isHttpAvatarUrl(w)) return String(w).trim()
  const raw = memberProfileRaw.value?.avatar_url
  if (raw != null && isHttpAvatarUrl(raw)) return String(raw).trim()
  return ''
})

const setupRowTitle = computed(() => {
  if (!needsMemberSetupPage.value) return ''
  const w = wxProfile.value?.nickName?.trim()
  if (w && w !== WX_DEFAULT_NICK) return w
  const un = userName.value?.trim()
  if (un && un !== MEMBER_STUB_NAME) return un
  const p = memberPhone.value
  if (p && p.length === 11) return `${p.slice(0, 3)}****${p.slice(-4)}`
  return '完善开卡资料'
})

const setupRowPhoneLine = computed(() => {
  if (!needsMemberSetupPage.value) return ''
  const p = memberPhone.value?.trim() || ''
  if (p.length === 11) return `${p.slice(0, 3)}****${p.slice(-4)}`
  return p || '请绑定手机号'
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

function onNickInput(e) {
  wxNickDraft.value = e.detail?.value ?? ''
}

function onNicknameBlurConfirm() {
  const nick = String(wxNickDraft.value || '').trim()
  if (!nick || nick === WX_DEFAULT_NICK) return
  const prev = wxProfile.value || { nickName: '', avatarUrl: '' }
  const p = { ...prev, nickName: nick }
  wxProfile.value = p
  persistWxProfile(p)
  const syncPayload = { wechat_name: nick }
  if (p.avatarUrl?.trim()) syncPayload.avatar_url = p.avatarUrl.trim()
  void pushWechatProfileToServer(syncPayload)
  if (!p.avatarUrl?.trim()) {
    uni.showToast({ title: '请点头像选择照片', icon: 'none' })
  } else if (!isPlaceholderWxProfile(p)) {
    uni.showToast({ title: '已保存', icon: 'success' })
  }
}

const profileSub = computed(() => {
  if (!isLoggedIn.value || needsMemberSetupPage.value) return ''
  const p = memberPhone.value
  if (p && p.length === 11) return `${p.slice(0, 3)}****${p.slice(-4)}`
  return ''
})


function shanghaiTodayYmd() {
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date())
    const y = parts.find((p) => p.type === 'year')?.value
    const m = parts.find((p) => p.type === 'month')?.value
    const d = parts.find((p) => p.type === 'day')?.value
    if (y && m && d) return `${y}-${m}-${d}`
  } catch {
    /* ignore */
  }
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

function isOnLeaveTodayShanghai() {
  const lr = leaveRange.value
  if (!lr || typeof lr !== 'object') return false
  const sRaw = lr.start != null ? String(lr.start).slice(0, 10) : ''
  const eRaw = lr.end != null ? String(lr.end).slice(0, 10) : ''
  if (!sRaw || !eRaw) return false
  const today = shanghaiTodayYmd()
  return today >= sRaw && today <= eRaw
}

/** 与后台配送口径一致：区间请假闭区间含「今日」则为请假中；「仅明天请假」不影响今日状态展示 */
const memberDeliveryStatus = computed(() => {
  if (!isLoggedIn.value || needsMemberSetupPage.value) return '尚未开启计划'
  if (isOnLeaveTodayShanghai()) return '请假中'
  return '配送中'
})

const planTypeMemberLabel = computed(() => {
  if (!isLoggedIn.value || needsMemberSetupPage.value) return ''
  const p = String(planType.value || '').trim()
  return p ? `${p}会员` : ''
})

const cardFooter = computed(() => {
  if (!isLoggedIn.value) return '自律，从今天第一顿 OK 饭开始 👌'
  const d = daysSinceCreated(createdAt.value)
  return `已陪伴您自律生活：${d} 天 👌`
})

const todayDeliveryAddressLine = computed(() => {
  const line = defaultAddrLine.value?.trim()
  if (line) return `今日送餐地址：${line}`
  return '今日送餐地址：未设置默认地址'
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
  isActive.value = !!data.is_active
  createdAt.value = data.created_at != null ? String(data.created_at) : ''

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

/** @param {{ prefetched?: object | null }} [options] 登录流程已请求过 GET /api/user/me 时可传入，避免重复请求 */
async function refreshMember(options = {}) {
  const token = getMemberToken()
  const phone = uni.getStorageSync('memberPhone') || ''
  isLoggedIn.value = !!token
  memberPhone.value = phone

  if (!isLoggedIn.value) {
    memberProfileRaw.value = null
    serverBalance.value = 0
    userName.value = ''
    planType.value = ''
    leaveRange.value = null
    isActive.value = false
    createdAt.value = ''
    wxProfile.value = null
    wxNickDraft.value = ''
    defaultAddrLine.value = ''
    syncDisplayNoAnim()
    return
  }

  loadWxProfileFromStorage()
  const pre = options.prefetched
  if (pre && typeof pre === 'object') {
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
    } catch (_) {
      memberProfileRaw.value = null
      serverBalance.value = 0
      userName.value = ''
      planType.value = ''
      leaveRange.value = null
      isActive.value = false
      createdAt.value = ''
    }
  }
  syncDisplayNoAnim()
}

onShow(() => {
  if (reLaunchIfCourierModePreferred()) return
  syncCustomTabBar()
  syncTabLayout()
  void refreshMember()
  void fetchDefaultAddressForCard()
  void loadMineCardPrices()
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
    await refreshMember({ prefetched: profile })
    uni.hideLoading()
    const snapshot = memberProfileRaw.value ?? profile
    const needSetup = shouldOpenMemberSetup(snapshot)
    if (needSetup) {
      setTimeout(() => {
        uni.navigateTo({
          url: '/packageUser/pages/memberSetup/memberSetup?from=login',
          fail: (e) => {
            console.error('navigateTo memberSetup', e)
            uni.showToast({ title: '无法打开完善资料页，请重试', icon: 'none' })
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
  uni.showModal({
    title: '套餐购买',
    content: `支付金额：¥${price}\n将为您增加 ${meals} 次餐次（演示：确认后本地累加，正式环境对接支付与后端）`,
    success: (res) => {
      if (!res.confirm) return
      addDemoCredits(meals)
      const nextTotal = serverBalance.value + getDemoCredits()
      animateBalanceTo(nextTotal)
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
  uni.navigateTo({ url: '/packageUser/pages/leave/leave' })
}
function goAddress() {
  uni.navigateTo({ url: '/packageUser/pages/address/list' })
}

function goMemberSetup() {
  uni.navigateTo({ url: '/packageUser/pages/memberSetup/memberSetup' })
}

async function loadMineCardPrices() {
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
    /* 使用默认值 */
  }
}

async function onMineCardPay(cardKind) {
  if (!showOpenCardRenewPanel.value || cardPayLoading.value) return
  const d0 = deliveryStartYmdFromProfile.value
  if (!d0) {
    uni.showToast({ title: '请先到完善资料页选择起送日期', icon: 'none' })
    goMemberSetup()
    return
  }
  cardPayLoading.value = true
  uni.showLoading({ title: '支付准备中…', mask: true })
  try {
    const { order } = await runMemberCardWechatPay({
      cardKind,
      deliveryStartYmd: d0,
      patchProfile: true,
    })
    uni.hideLoading()
    const amt = order && typeof order.amount_yuan === 'string' ? order.amount_yuan : ''
    uni.showModal({
      title: '支付成功',
      content: amt
        ? `已支付 ¥${amt}。剩余次数将在微信通知确认后到账，请稍候查看。`
        : '支付已完成，剩余次数将在微信通知确认后到账。',
      showCancel: false,
      success: () => {
        void refreshMember()
        void fetchDefaultAddressForCard()
      },
    })
  } catch (err) {
    uni.hideLoading()
    const raw = err && typeof err === 'object' ? err : {}
    const errMsg = typeof raw.errMsg === 'string' ? raw.errMsg : ''
    if (errMsg.includes('cancel') || errMsg.includes('取消')) {
      uni.showToast({ title: '已取消支付', icon: 'none' })
    } else {
      uni.showToast({
        title: err instanceof Error ? err.message : errMsg || '支付失败',
        icon: 'none',
        duration: 2800,
      })
    }
  } finally {
    cardPayLoading.value = false
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
  background: $ok-slate-50;
}

.profile-container {
  padding: 40rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
}

.user-header {
  display: flex;
  align-items: center;
  gap: 30rpx;
  margin-bottom: 50rpx;
}

.user-header--setup {
  padding: 8rpx 0;
  box-sizing: border-box;
}

.avatar-box--setup {
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
  border-color: #fff8e7;
}

.setup-chevron {
  margin-left: auto;
  font-size: 44rpx;
  font-weight: 300;
  color: #cbd5e1;
  line-height: 1;
  flex-shrink: 0;
}

.avatar-btn {
  padding: 0;
  margin: 0;
  background: transparent;
  border: none;
  line-height: 0;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  height: auto;
  min-height: 0;
  align-self: center;
}

.avatar-btn::after {
  border: none;
}

.user-name-box--flex {
  flex: 1;
  min-width: 0;
  position: relative;
}

.nick-field-wrap {
  position: relative;
  width: 100%;
}

/* 仅昵称一行时：与左侧头像（含白边约 140rpx）垂直居中对齐 */
.user-name-box--center-col {
  min-height: 140rpx;
  justify-content: center;
  gap: 0;
}

.nick-guide {
  display: block;
  font-size: 22rpx;
  color: $ok-slate-400;
  font-weight: 700;
  line-height: 1.4;
  margin-bottom: 12rpx;
}

.nick-input {
  width: 100%;
  font-size: 40rpx;
  font-weight: 950;
  color: $ok-slate-800;
  padding: 12rpx 0;
  margin-bottom: 4rpx;
  border-bottom: 2rpx solid $ok-slate-200;
  box-sizing: border-box;
  line-height: 1.35;
}

/* 真机 placeholder 易不可见：text 叠在条上且 pointer-events:none，点击穿透到 input */
.nick-static-label {
  position: absolute;
  left: 36rpx;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  font-size: 30rpx;
  font-weight: 700;
  color: #64748b;
  z-index: 2;
  max-width: calc(100% - 72rpx);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 完善资料：圆角条；输入文字用实色 hex，避免真机继承成白字 */
.nick-input--single {
  position: relative;
  z-index: 1;
  border: none;
  border-bottom: none;
  background: #f1f5f9;
  border-radius: 999rpx;
  padding: 22rpx 36rpx;
  margin-bottom: 0;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 1.5;
  color: #0f172a;
  min-height: 88rpx;
  box-sizing: border-box;
}

.nick-placeholder {
  color: #64748b;
  font-weight: 700;
}

.nick-hint {
  margin-top: 8rpx;
}

/* 微信 getPhoneNumber：整行可点，样式与普通头部一致 */
.user-header--wx {
  margin: 0 0 50rpx;
  padding: 0;
  width: 100%;
  background: transparent;
  border: none;
  line-height: normal;
  text-align: left;
  box-sizing: border-box;
}

.user-header--wx::after {
  border: none;
}

.avatar-box {
  width: 128rpx;
  height: 128rpx;
  border-radius: 50%;
  background: $ok-forest-green;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 6rpx solid #fff;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.1);
  overflow: hidden;
  flex-shrink: 0;
}

.avatar-img {
  width: 100%;
  height: 100%;
  display: block;
}

.avatar-box--guest {
  background: #94a3b8;
  border-color: #e2e8f0;
}

.avatar-txt {
  font-size: 48rpx;
  font-weight: 900;
  color: #fff;
}

.avatar-txt--guest {
  font-size: 64rpx;
  font-weight: 950;
}

/* 待选头像占位：显示「点」 */
.avatar-txt--dot {
  font-size: 56rpx;
  font-weight: 950;
  letter-spacing: 0;
}

.user-name-box {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.nick-name {
  font-size: 44rpx;
  font-weight: 950;
  color: #0f172a;
}

.nick-name--action {
  color: $ok-forest-green;
}

.level-text {
  font-size: 24rpx;
  color: #334155;
  font-weight: 700;
}

.vip-card {
  background: $ok-forest-green;
  border-radius: 70rpx;
  padding: 56rpx;
  color: #fff;
  margin-bottom: 60rpx;
  box-shadow: 0 40rpx 80rpx rgba(14, 90, 68, 0.25);
}

.vip-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  flex-wrap: wrap;
  margin-bottom: 36rpx;
}

.vip-tag {
  display: inline-block;
  font-size: 20rpx;
  font-weight: 950;
  background: rgba(255, 255, 255, 0.15);
  padding: 10rpx 24rpx;
  border-radius: 20rpx;
  letter-spacing: 2rpx;
}

.member-plan-kind {
  font-size: 26rpx;
  font-weight: 950;
  color: $ok-sunshine-yellow;
  letter-spacing: 1rpx;
}

.balance-line {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 16rpx;
}

.num {
  font-size: 120rpx;
  font-weight: 950;
  color: $ok-sunshine-yellow;
  letter-spacing: -4rpx;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.unit {
  font-size: 30rpx;
  font-weight: 900;
  opacity: 0.8;
}

.type-label {
  flex: 1;
  text-align: right;
  font-weight: 950;
  font-style: italic;
  color: $ok-sunshine-yellow;
  font-size: 30rpx;
  min-width: 200rpx;
}

.today-delivery-addr {
  display: block;
  font-size: 24rpx;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.92);
  margin-top: 28rpx;
  line-height: 1.45;
  text-align: left;
}

.footer-info {
  display: block;
  font-size: 22rpx;
  opacity: 0.6;
  font-weight: 800;
  margin-top: 20rpx;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding-top: 24rpx;
}

.open-card-banner {
  margin-bottom: 40rpx;
  padding: 36rpx 32rpx 28rpx;
  background: #fff;
  border-radius: 40rpx;
  border: 3rpx solid $ok-slate-100;
  box-shadow: 0 12rpx 40rpx rgba(15, 23, 42, 0.06);
}

.open-card-banner-title {
  display: block;
  font-size: 34rpx;
  font-weight: 950;
  color: $ok-slate-800;
  margin-bottom: 12rpx;
}

.open-card-banner-desc {
  display: block;
  font-size: 24rpx;
  font-weight: 700;
  color: $ok-slate-500;
  line-height: 1.5;
  margin-bottom: 28rpx;
}

.open-card-cards {
  margin-bottom: 8rpx;
}

.sub-plan-item--disabled {
  opacity: 0.55;
  pointer-events: none;
}

.open-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 8rpx 0;
  margin-top: 8rpx;
  border-top: 1rpx solid $ok-slate-100;
}

.open-card-foot-text {
  font-size: 24rpx;
  font-weight: 800;
  color: $ok-forest-green;
}

.open-card-foot-arrow {
  font-size: 32rpx;
  color: #cbd5e1;
  font-weight: 300;
}

.plan-purchase-title {
  padding-bottom: 30rpx;
}

.plan-h3 {
  font-size: 36rpx;
  font-weight: 950;
  color: $ok-forest-green;
}

.subscription-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24rpx;
  margin-bottom: 28rpx;
}

.sub-plan-item {
  background: #fff;
  border-radius: 48rpx;
  padding: 40rpx 30rpx;
  border: 3rpx solid $ok-slate-100;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  min-height: 200rpx;
}

.sub-plan-item.highlight {
  border-color: $ok-sunshine-yellow;
  background: #fffdf5;
}

.rec-badge {
  position: absolute;
  top: -20rpx;
  right: 20rpx;
  background: $ok-sunshine-yellow;
  color: $ok-forest-green;
  font-size: 16rpx;
  font-weight: 950;
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
}

.plan-en {
  display: block;
  font-size: 18rpx;
  font-weight: 900;
  color: $ok-slate-400;
  margin-bottom: 8rpx;
}

.plan-name {
  display: block;
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-slate-800;
}

.plan-price {
  font-size: 44rpx;
  font-weight: 1000;
  font-style: italic;
  color: $ok-forest-green;
  margin-top: 10rpx;
}

.yen {
  font-size: 24rpx;
  font-style: normal;
}

.action-list {
  background: #fff;
  border-radius: 48rpx;
  overflow: hidden;
  border: 1px solid $ok-slate-100;
  margin-bottom: 0;
}

.menu-row {
  padding: 44rpx 40rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid $ok-slate-50;
}

.menu-row:last-child {
  border-bottom: none;
}

.menu-row--muted {
  opacity: 0.6;
  margin-top: 20rpx;
}

.menu-label {
  font-size: 30rpx;
  font-weight: 900;
  color: #333;
}

.menu-label--small {
  font-size: 24rpx;
}

.arrow {
  color: #ccc;
  font-size: 40rpx;
}
</style>
