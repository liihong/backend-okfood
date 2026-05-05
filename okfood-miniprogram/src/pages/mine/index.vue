<template>
  <view class="page" :style="pageStyle">
    <OkNavbar show-brand />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="profile-container">
        <view v-if="!isLoggedIn" class="user-header user-header--guest">
          <view :class="['avatar-box', 'avatar-box--guest']">
            <text class="avatar-txt avatar-txt--guest">?</text>
          </view>
          <view class="user-header-guest-main">
            <button
              class="wx-login-btn"
              hover-class="wx-login-btn--hover"
              open-type="getPhoneNumber"
              @getphonenumber="onWxGetPhoneNumber"
            >
              登录
            </button>
            <text class="level-text level-text--guest-hint">
              授权手机号后与会员档案、餐次同步
            </text>
          </view>
        </view>
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

        <view :class="['vip-card', { 'vip-card--month': isVipMonthlyCard }]">
          <view class="vip-card-head">
            <text class="vip-tag">OK 饭 自律计划</text>
            <text v-if="planTypeMemberLabel" class="member-plan-kind">{{ planTypeMemberLabel }}</text>
          </view>
          <view class="balance-line">
            <text class="num">{{ displayBalance }}</text>
            <text class="unit">剩余餐次</text>
            <view
              v-if="showResumeDeliveryEntry"
              class="type-label-slot"
              @tap.stop="goResumeDelivery"
            >
              <text class="vip-renew-btn">恢复配送</text>
            </view>
            <view
              v-else-if="showVipRenewEntry"
              class="type-label-slot"
              @tap.stop="goMemberSetup"
            >
              <text class="vip-renew-btn">开卡续费</text>
            </view>
            <text v-else :class="['type-label', { 'type-label--leave-detail': isLeaveCardDetailStatus }]">{{
              memberDeliveryStatus }}</text>
          </view>
          <text v-if="isLoggedIn" class="today-delivery-addr">{{ todayDeliveryAddressLine }}</text>
          <view class="footer-info">
            <text class="footer-info-left">{{ cardFooter }}</text>
            <text v-if="isLoggedIn" class="footer-info-right"
              >每日送达份数：{{ displayDailyMealUnits }}</text>
          </view>
        </view>

        <view class="action-list">
          <view v-if="!isLoggedIn" class="menu-row" @click="goCourier">
            <text class="menu-label">配送员工作台</text>
            <text class="arrow">›</text>
          </view>
          <view class="menu-row" @click="goDailyMealUnits">
            <text class="menu-label">📦 修改每日送达份数</text>
            <text class="arrow">›</text>
          </view>
          <view class="menu-row" @click="goLeave">
            <text class="menu-label">😴 请假管理</text>
            <text class="arrow">›</text>
          </view>
          <view
            v-if="showPauseDeliveryMenuRow"
            class="menu-row"
            @click="onPauseDeliveryTap"
          >
            <text class="menu-label">⏸️ 暂停配送</text>
            <text class="arrow">›</text>
          </view>
          <view class="menu-row" @click="goAddress">
            <text class="menu-label">🏠 地址管理</text>
            <text class="arrow">›</text>
          </view>
          <view class="menu-row" @click="goSingleOrders">
            <text class="menu-label">🧾 我的单次订单</text>
            <text class="arrow">›</text>
          </view>
        </view>
        <text class="page-version">版本 1.1.5</text>
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
  clearMemberSession,
  isUserMeNotFoundError,
} from '@/utils/api.js'
import { wxMiniMemberLoginAndStore, hasWxPhoneAuthDetail } from '@/utils/wxMemberLogin.js'
import {
  shouldOpenMemberSetup,
  shouldPromptMemberCardPay,
  isDeliveryPausedWithBalance,
  isPlaceholderWxProfile,
  MEMBER_STUB_NAME,
  WX_DEFAULT_NICK,
} from '@/utils/memberProfile.js'
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
/** 默认配送地址展示行（详细地址，与地址列表一致，不含所属片区） */
const defaultAddrLine = ref('')
let fetchDefaultAddrSeq = 0

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

/** 开卡/续费区：与「完善资料」解耦，仅看服务端剩余餐次是否为 0（用于绿卡「开卡续费」按钮） */
const showMemberCardModule = computed(() => {
  if (!isLoggedIn.value) return false
  const p = memberProfileRaw.value
  if (p && typeof p === 'object') return shouldPromptMemberCardPay(p)
  return serverBalance.value <= 0
})

/** 有余额且暂停配送：会员卡右侧展示「恢复配送」（与「开卡续费」互斥；资料待完善也可点此进入资料页恢复） */
const showResumeDeliveryEntry = computed(() => {
  if (!isLoggedIn.value) return false
  return isDeliveryPausedWithBalance(memberProfileRaw.value)
})

/** 绿区右侧：剩余次数为 0 或资料待完善时展示「开卡续费」；暂停且有次数时不展示 */
const showVipRenewEntry = computed(() => {
  if (!isLoggedIn.value || showResumeDeliveryEntry.value) return false
  return needsMemberSetupPage.value || showMemberCardModule.value
})

/** 仍有餐次且当前未暂停：菜单中提供一键暂停（等同资料页「暂停配送」选项） */
const showPauseDeliveryMenuRow = computed(() => {
  if (!isLoggedIn.value || needsMemberSetupPage.value) return false
  const p = memberProfileRaw.value
  if (!p || typeof p !== 'object') return false
  if (p.delivery_deferred === true) return false
  return Math.max(0, Math.floor(Number(p.balance) || 0)) > 0
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
  const p = String(memberPhone.value || '').trim()
  if (p) return p
  return '点我：完善个人资料'
})

const setupRowPhoneLine = computed(() => {
  if (!needsMemberSetupPage.value) return ''
  const p = memberPhone.value?.trim() || ''
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
  return String(memberPhone.value || '').trim()
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

/** 已设置区间起止（含「尚未开始」的未来区间），与请假页 isOnLeaveNow 中区间部分一致 */
function hasLeaveRangeConfigured() {
  const lr = leaveRange.value
  if (!lr || typeof lr !== 'object') return false
  const sRaw = lr.start != null ? String(lr.start).slice(0, 10) : ''
  const eRaw = lr.end != null ? String(lr.end).slice(0, 10) : ''
  return Boolean(sRaw && eRaw)
}

function ymdFromApi(d) {
  if (d == null || d === '') return ''
  const s = String(d)
  return s.length >= 10 ? s.slice(0, 10) : s
}

/** 展示用：月.日，如 10.12；与 leave 页区间格式一致 */
function ymdToDotMd(ymd) {
  const raw = ymdFromApi(ymd)
  if (!raw) return ''
  const parts = raw.split('-')
  if (parts.length < 3) return ''
  const m = Number(parts[1])
  const d = Number(parts[2])
  if (!m || !d) return ''
  return `${m}.${d}`
}

/** 与后台一致：区间、仅明日请假；含「已提交未来区间」；文案展示具体日期 */
const isLeaveCardDetailStatus = computed(
  () => isOnLeaveTodayShanghai() || isLeavedTomorrow.value || hasLeaveRangeConfigured(),
)

const memberDeliveryStatus = computed(() => {
  if (!isLoggedIn.value) return '尚未开启计划'
  if (needsMemberSetupPage.value) return '资料待完善'
  if (isOnLeaveTodayShanghai() || isLeavedTomorrow.value || hasLeaveRangeConfigured()) {
    if (isOnLeaveTodayShanghai()) {
      const lr = leaveRange.value
      const sRaw = lr?.start != null ? String(lr.start).slice(0, 10) : ''
      const eRaw = lr?.end != null ? String(lr.end).slice(0, 10) : ''
      const sm = ymdToDotMd(sRaw)
      const em = ymdToDotMd(eRaw)
      if (sm && em) {
        if (sRaw === eRaw) return `${sm} 请假`
        return `${sm}-${em} 请假`
      }
      return '请假中'
    }
    if (hasLeaveRangeConfigured() && !isOnLeaveTodayShanghai()) {
      const lr = leaveRange.value
      const sRaw = lr?.start != null ? String(lr.start).slice(0, 10) : ''
      const eRaw = lr?.end != null ? String(lr.end).slice(0, 10) : ''
      const sm = ymdToDotMd(sRaw)
      const em = ymdToDotMd(eRaw)
      if (sm && em) {
        if (sRaw === eRaw) return `${sm} 起请假`
        return `${sm}-${em} 请假`
      }
      return '已预约请假'
    }
    if (isLeavedTomorrow.value) {
      const t = tomorrowLeaveTargetYmd.value
      const md = t ? ymdToDotMd(t) : ''
      if (md) return `${md} 请假`
      return '请假中'
    }
    return '请假中'
  }
  if (isDeliveryPausedWithBalance(memberProfileRaw.value)) return '暂停配送'
  if (showMemberCardModule.value) return '待开卡/续费'
  return '生效中'
})

const planTypeMemberLabel = computed(() => {
  if (!isLoggedIn.value || needsMemberSetupPage.value) return ''
  const p = String(planType.value || '').trim()
  return p ? `${p}会员` : ''
})

/** 月卡：会员卡采用独立配色，与周卡绿区形成区分 */
const isVipMonthlyCard = computed(
  () => isLoggedIn.value && !needsMemberSetupPage.value && String(planType.value || '').trim() === '月卡',
)

const cardFooter = computed(() => {
  if (!isLoggedIn.value) return '自律，从今天第一顿 OK 饭开始 👌'
  const d = daysSinceCreated(createdAt.value)
  return `已陪伴您自律生活：${d} 天 👌`
})

const displayDailyMealUnits = computed(() => {
  const n = Math.floor(Number(dailyMealUnits.value) || 0)
  return n >= 1 ? Math.min(50, n) : 1
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
    isLeavedTomorrow.value = false
    tomorrowLeaveTargetYmd.value = ''
    isActive.value = false
    createdAt.value = ''
    dailyMealUnits.value = 1
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
    } catch (e) {
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
  syncDisplayNoAnim()
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
  void refreshMember()
  void fetchDefaultAddressForCard()
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

function goSingleOrders() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/packageOrder/pages/singleOrderList/singleOrderList' })
}

function goDailyMealUnits() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/packageUser/pages/dailyMealUnits/dailyMealUnits' })
}

function goMemberSetup() {
  uni.navigateTo({ url: '/packageUser/pages/memberSetup/memberSetup' })
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
  uni.showModal({
    title: '暂停配送',
    content:
      '确认后暂停会员卡配送（剩余餐次保留）。恢复时需重新选择开始的业务日期。是否暂停？',
    confirmText: '暂停配送',
    cancelText: '取消',
    success: async (res) => {
      if (!res.confirm) return
      uni.showLoading({ title: '提交中', mask: true })
      try {
        await request('/api/user/profile', {
          method: 'PATCH',
          data: { delivery_deferred: true },
        })
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

.user-header--guest {
  align-items: center;
}

.user-header-guest-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 16rpx;
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

.level-text--guest-hint {
  font-size: 24rpx;
  color: $ok-slate-500;
  line-height: 1.45;
}

/* 微信授权手机号：与说明同宽、偏大的主按钮 */
.wx-login-btn {
  margin: 0;
  padding: 26rpx 40rpx;
  width: 100%;
  max-width: 420rpx;
  box-sizing: border-box;
  font-size: 34rpx;
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

/* 月卡：深靛紫渐变 + 香槟金强调，与周卡绿金区分 */
.vip-card--month {
  background: linear-gradient(165deg, #1a2744 0%, #2d2248 42%, #121c32 100%);
  box-shadow:
    0 40rpx 100rpx rgba(8, 10, 28, 0.52),
    0 0 0 1rpx rgba(212, 175, 55, 0.22);
}

.vip-card--month .vip-tag {
  color: #f5ead6;
  background: rgba(255, 220, 160, 0.12);
  border: 1rpx solid rgba(212, 175, 55, 0.38);
}

.vip-card--month .member-plan-kind {
  color: #ffd98a;
  text-shadow: 0 2rpx 10rpx rgba(0, 0, 0, 0.35);
}

.vip-card--month .num {
  color: #ffe082;
  text-shadow: 0 4rpx 20rpx rgba(255, 200, 90, 0.22);
}

.vip-card--month .unit {
  color: #e8e0d5;
  opacity: 0.95;
}

.vip-card--month .type-label {
  color: #ffd98a;
}

.vip-card--month .type-label--leave-detail {
  color: #f0c97a;
}

.vip-card--month .vip-renew-btn {
  color: #1a1f2e;
  background: linear-gradient(180deg, #fff0c2 0%, #e8b84a 100%);
  box-shadow: 0 8rpx 28rpx rgba(0, 0, 0, 0.32);
  border: 1rpx solid rgba(255, 255, 255, 0.35);
}

.vip-card--month .today-delivery-addr {
  color: rgba(255, 248, 235, 0.94);
}

.vip-card--month .footer-info {
  color: rgba(230, 215, 190, 0.82);
  opacity: 0.88;
  border-top-color: rgba(212, 175, 55, 0.22);
}

.vip-card--month .footer-info-right {
  color: rgba(230, 215, 190, 0.88);
  opacity: 0.9;
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

/* 区间 / 明日 等略长文案，略缩小以免挤压剩余餐次数字 */
.type-label--leave-detail {
  font-size: 24rpx;
  line-height: 1.25;
}
.type-label-slot {
  flex: 1;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  min-width: 200rpx;
}

.vip-renew-btn {
  font-size: 26rpx;
  font-weight: 950;
  font-style: normal;
  color: $ok-forest-green;
  background: $ok-sunshine-yellow;
  padding: 14rpx 32rpx;
  border-radius: 999rpx;
  line-height: 1.2;
  box-shadow: 0 6rpx 20rpx rgba(0, 0, 0, 0.12);
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
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20rpx;
  flex-wrap: wrap;
  font-size: 22rpx;
  opacity: 0.6;
  font-weight: 800;
  margin-top: 20rpx;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding-top: 24rpx;
}

.footer-info-left {
  flex: 1;
  min-width: 0;
  line-height: 1.35;
}

.footer-info-right {
  flex-shrink: 0;
  text-align: right;
  line-height: 1.35;
  font-size: 22rpx;
  font-weight: 800;
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
