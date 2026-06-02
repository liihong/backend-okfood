<template>
  <view class="page">
    <OkNavbar :show-back="showBack" title="设置昵称" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="wrap">
        <text class="lead">{{ leadText }}</text>

        <view class="profile-card">
          <text class="sec-title">您的称呼</text>
          <text class="sec-sub">便于客服与配送识别，请填写真实姓名或常用昵称</text>
          <input
            class="nick-input"
            type="nickname"
            v-model="nickDraft"
            placeholder="请输入姓名或昵称"
            placeholder-class="nick-input-ph"
            maxlength="32"
            confirm-type="done"
            :focus="nickInputFocus"
            @input="onNickInput"
            @blur="onNickBlur"
            @confirm="onSubmit"
          />

          <text class="sec-title sec-title--sp sec-title--optional">头像（选填）</text>
          <view class="avatar-section">
            <button
              class="avatar-btn"
              open-type="chooseAvatar"
              hover-class="avatar-btn--hover"
              @chooseavatar="onChooseAvatar"
            >
              <view class="avatar-ring avatar-ring--sm">
                <image
                  v-if="avatarUrl"
                  class="avatar-img"
                  :src="avatarUrl"
                  mode="aspectFill"
                />
                <text v-else class="avatar-fallback">{{ avatarFallbackChar }}</text>
              </view>
              <text class="avatar-tip">点击上传，可跳过</text>
            </button>
          </view>
        </view>

        <button class="submit-btn" :loading="submitting" @click="onSubmit">
          完成并进入我的
        </button>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getPageScrollStyle } from '@/utils/navbar.js'
import {
  request,
  getMemberToken,
  uploadMemberAvatarFile,
  clearMemberSession,
  isUserMeNotFoundError,
} from '@/utils/api.js'
import {
  shouldCompleteMemberProfile,
  MEMBER_STUB_NAME,
  WX_DEFAULT_NICK,
} from '@/utils/memberProfile.js'
import {
  loadWxProfile,
  persistWxProfile,
  pushWechatProfileToServer,
  isValidWxNick,
} from '@/utils/memberWxProfile.js'
import { markMinePageNeedsRefresh } from '@/utils/minePageRefresh.js'

const scrollStyle = ref({})

function applyScrollLayout() {
  scrollStyle.value = getPageScrollStyle()
}

/** login：登录后强制完善；required：已登录但资料不全时兜底引导 */
const entryFrom = ref('')
const submitting = ref(false)
const memberProfileRaw = ref(null)
const avatarUrl = ref('')
const nickDraft = ref('')
const nickInputFocus = ref(false)

const showBack = computed(() => entryFrom.value !== 'login' && entryFrom.value !== 'required')

const leadText = computed(() => {
  if (entryFrom.value === 'login') {
    return '欢迎加入 OK 饭！请先设置您的称呼，方便客服为您服务。'
  }
  return '请设置您的称呼，方便客服识别与联系。'
})

const avatarFallbackChar = computed(() => {
  const nick = String(nickDraft.value || '').trim()
  if (nick && nick !== WX_DEFAULT_NICK && nick !== MEMBER_STUB_NAME) {
    const ch = nick[0]
    return /[\u4e00-\u9fa5]/.test(ch) ? ch : (nick[0] || 'O').toUpperCase()
  }
  return '待'
})

function mergeProfileToForm(data) {
  memberProfileRaw.value = data && typeof data === 'object' ? data : null
  if (!data || typeof data !== 'object') return

  const av = data.avatar_url != null ? String(data.avatar_url).trim() : ''
  const wnRaw = data.wechat_name != null ? String(data.wechat_name).trim() : ''
  const wn = wnRaw && wnRaw !== WX_DEFAULT_NICK ? wnRaw : ''
  const nm = data.name != null ? String(data.name).trim() : ''
  const nameOk = nm && nm !== MEMBER_STUB_NAME ? nm : ''
  const nickFromServer = wn || nameOk

  const local = loadWxProfile(data.phone != null ? String(data.phone) : '')
  avatarUrl.value = av || (local?.avatarUrl?.trim() || '')
  const currentDraft = String(nickDraft.value || '').trim()
  // 保留用户已填但未保存的昵称，避免 onShow / 选头像后刷新覆盖
  if (isValidWxNick(currentDraft)) return
  nickDraft.value =
    nickFromServer ||
    (local?.nickName && local.nickName !== WX_DEFAULT_NICK ? local.nickName.trim() : '')
}

async function refreshProfile() {
  if (!getMemberToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/mine/index' })
    }, 400)
    return
  }
  try {
    const data = await request('/api/user/me', { method: 'GET' })
    mergeProfileToForm(data)
    if (!shouldCompleteMemberProfile(data) && entryFrom.value) {
      finishAndGoMine({ toast: '' })
    }
  } catch (e) {
    if (isUserMeNotFoundError(e)) {
      clearMemberSession()
      uni.switchTab({ url: '/pages/mine/index' })
      return
    }
    uni.showToast({ title: e?.message || '加载资料失败', icon: 'none' })
  }
}

async function onChooseAvatar(e) {
  const localPath = e.detail?.avatarUrl
  if (!localPath) return
  uni.showLoading({ title: '上传头像…', mask: true })
  try {
    const permanentUrl = await uploadMemberAvatarFile(localPath)
    avatarUrl.value = permanentUrl
    const syncPayload = { avatar_url: permanentUrl }
    if (isValidWxNick(nickDraft.value)) syncPayload.wechat_name = nickDraft.value.trim()
    await pushWechatProfileToServer(syncPayload, { showErrorToast: false })
    persistWxProfile({
      nickName: isValidWxNick(nickDraft.value) ? nickDraft.value.trim() : '',
      avatarUrl: permanentUrl,
    })
    if (memberProfileRaw.value && typeof memberProfileRaw.value === 'object') {
      memberProfileRaw.value = { ...memberProfileRaw.value, avatar_url: permanentUrl }
    }
    uni.showToast({ title: '头像已上传', icon: 'success' })
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

function syncNickFromEvent(e) {
  const v = e?.detail?.value
  if (v != null && String(v).trim()) {
    nickDraft.value = String(v).trim()
  }
}

function onNickInput(e) {
  syncNickFromEvent(e)
}

function onNickBlur(e) {
  syncNickFromEvent(e)
}

/** 提交前先收起键盘，确保微信昵称一键填入后 blur 能同步到 nickDraft */
function awaitNickInputSettled() {
  return new Promise((resolve) => {
    nickInputFocus.value = false
    uni.hideKeyboard({
      complete: () => {
        setTimeout(resolve, 100)
      },
    })
  })
}

function finishAndGoMine({ toast }) {
  markMinePageNeedsRefresh()
  if (toast) {
    try {
      uni.setStorageSync('okfood_pending_mine_toast', toast)
    } catch {
      /* ignore */
    }
  }
  uni.switchTab({ url: '/pages/mine/index' })
}

async function onSubmit(e) {
  syncNickFromEvent(e)
  await awaitNickInputSettled()
  const nick = String(nickDraft.value || '').trim()
  if (!isValidWxNick(nick)) {
    uni.showToast({ title: '请填写姓名或昵称', icon: 'none' })
    return
  }
  if (submitting.value) return
  submitting.value = true
  uni.showLoading({ title: '保存中', mask: true })
  try {
    const body = { wechat_name: nick }
    const av = avatarUrl.value.trim()
    if (av) body.avatar_url = av
    await pushWechatProfileToServer(body, { showErrorToast: false })
    persistWxProfile({ nickName: nick, avatarUrl: av })
    uni.hideLoading()
    const toastMsg = entryFrom.value === 'login' ? '登录成功' : '昵称已保存'
    finishAndGoMine({ toast: toastMsg })
  } catch (err) {
    uni.hideLoading()
    uni.showToast({ title: err?.message || '保存失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

onLoad((query) => {
  applyScrollLayout()
  entryFrom.value = query?.from != null ? String(query.from) : ''
  nextTick(() => {
    nickInputFocus.value = true
  })
})

onShow(() => {
  applyScrollLayout()
  void refreshProfile()
})
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  box-sizing: border-box;
  background: $ok-slate-50;
  display: flex;
  flex-direction: column;
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
}

.wrap {
  padding: 24rpx 32rpx 48rpx;
  box-sizing: border-box;
}

.lead {
  display: block;
  font-size: 28rpx;
  font-weight: 700;
  color: $ok-slate-600;
  line-height: 1.55;
  margin-bottom: 28rpx;
}

.profile-card {
  padding: 32rpx 28rpx;
  background: #fff;
  border-radius: 24rpx;
  border: 2rpx solid $ok-slate-100;
  box-sizing: border-box;
  margin-bottom: 32rpx;
}

.sec-title {
  display: block;
  font-size: 30rpx;
  font-weight: 950;
  color: $ok-slate-800;
  margin-bottom: 20rpx;
}

.sec-title--sp {
  margin-top: 28rpx;
}

.sec-title--optional {
  font-size: 26rpx;
  font-weight: 800;
  color: $ok-slate-500;
}

.sec-sub {
  display: block;
  font-size: 22rpx;
  color: $ok-slate-500;
  font-weight: 700;
  margin: -8rpx 0 20rpx;
  line-height: 1.4;
}

.avatar-section {
  display: flex;
  justify-content: center;
  margin-bottom: 16rpx;
}

.avatar-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
  padding: 0;
  margin: 0;
  background: transparent;
  border: none;
  line-height: normal;
}

.avatar-btn::after {
  border: none;
}

.avatar-btn--hover {
  opacity: 0.88;
}

.avatar-ring {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: $ok-slate-100;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.avatar-ring--sm {
  border: 2rpx dashed $ok-slate-200;
  box-shadow: none;
}

.avatar-img {
  width: 100%;
  height: 100%;
}

.avatar-fallback {
  font-size: 44rpx;
  font-weight: 800;
  color: $ok-slate-400;
}

.avatar-tip {
  font-size: 22rpx;
  font-weight: 600;
  color: $ok-slate-400;
}

.nick-input {
  width: 100%;
  box-sizing: border-box;
  height: 88rpx;
  padding: 0 28rpx;
  background: $ok-slate-50;
  border-radius: 16rpx;
  border: 2rpx solid $ok-slate-100;
  font-size: 30rpx;
  font-weight: 700;
  color: $ok-slate-800;
}

.nick-input-ph {
  color: $ok-slate-400;
  font-weight: 600;
}

.submit-btn {
  width: 100%;
  height: 96rpx;
  line-height: 96rpx;
  border-radius: 999rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 32rpx;
  font-weight: 900;
  border: none;
}

.submit-btn::after {
  border: none;
}
</style>
