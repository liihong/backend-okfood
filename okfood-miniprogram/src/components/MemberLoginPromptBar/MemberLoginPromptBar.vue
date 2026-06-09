<template>
  <view v-if="guestVisible" class="member-login-bar">
    <text class="member-login-bar__text">登录后享受完整会员服务</text>
    <button
      class="member-login-bar__btn"
      hover-class="member-login-bar__btn--hover"
      open-type="getPhoneNumber"
      @getphonenumber="onWxGetPhoneNumber"
    >
      立即登录
    </button>
  </view>
  <view v-else-if="loggedInVisible" class="member-user-bar">
    <view class="member-user-bar__profile">
      <view class="member-user-bar__avatar-wrap">
        <image
          v-if="avatarUrl"
          class="member-user-bar__avatar"
          :src="avatarUrl"
          mode="aspectFill"
        />
        <text v-else class="member-user-bar__avatar-fallback">{{ avatarChar }}</text>
      </view>
      <text class="member-user-bar__name">{{ displayName }}</text>
    </view>
    <button
      class="member-user-bar__btn"
      hover-class="member-user-bar__btn--hover"
      @tap="goMemberCenter"
    >
      会员中心
    </button>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getMemberToken, request } from '@/utils/api.js'
import {
  hasWxPhoneAuthDetail,
  wxMiniMemberLoginAndStore,
} from '@/utils/wxMemberLogin.js'
import {
  loadWxProfile,
  memberAvatarFallbackChar,
  resolveMemberAvatarUrl,
  resolveMemberDisplayName,
} from '@/utils/memberWxProfile.js'

const emit = defineEmits(['logged-in'])

const guestVisible = ref(false)
const loggedInVisible = ref(false)
const wxProfile = ref(null)
const serverProfile = ref(null)
const memberPhone = ref('')
let syncSeq = 0

const displayName = computed(() =>
  resolveMemberDisplayName({
    wxProfile: wxProfile.value,
    serverProfile: serverProfile.value,
    phone: memberPhone.value,
  }),
)

const avatarUrl = computed(() =>
  resolveMemberAvatarUrl({
    wxProfile: wxProfile.value,
    serverProfile: serverProfile.value,
  }),
)

const avatarChar = computed(() => memberAvatarFallbackChar(displayName.value))

async function syncState() {
  const seq = ++syncSeq
  const token = getMemberToken()
  const phone = uni.getStorageSync('memberPhone') || ''
  memberPhone.value = phone

  if (!token) {
    guestVisible.value = true
    loggedInVisible.value = false
    wxProfile.value = null
    serverProfile.value = null
    return
  }

  guestVisible.value = false
  loggedInVisible.value = true
  wxProfile.value = loadWxProfile(phone)

  try {
    const data = await request('/api/user/me', { method: 'GET' })
    if (seq !== syncSeq) return
    serverProfile.value = data && typeof data === 'object' ? data : null
    const sp = data?.phone != null ? String(data.phone).trim() : ''
    if (sp) {
      memberPhone.value = sp
      wxProfile.value = loadWxProfile(sp)
    }
  } catch {
    if (seq !== syncSeq) return
    serverProfile.value = null
  }
}

async function onWxGetPhoneNumber(e) {
  const detail = e?.detail
  if (!hasWxPhoneAuthDetail(detail)) {
    if (detail?.errMsg && !String(detail.errMsg).includes('cancel')) {
      uni.showToast({ title: '需要授权手机号', icon: 'none' })
    }
    return
  }
  uni.showLoading({ title: '登录中', mask: true })
  try {
    const { profile } = await wxMiniMemberLoginAndStore(detail)
    emit('logged-in')
    uni.showToast({ title: '登录成功', icon: 'success' })
    if (profile && typeof profile === 'object') {
      serverProfile.value = profile
      const sp = profile.phone != null ? String(profile.phone).trim() : ''
      if (sp) memberPhone.value = sp
    }
    await syncState()
  } catch (err) {
    uni.showToast({
      title: err instanceof Error ? err.message : '登录失败',
      icon: 'none',
    })
  } finally {
    uni.hideLoading()
  }
}

function goMemberCenter() {
  uni.switchTab({ url: '/pages/mine/index' })
}

onMounted(syncState)
onShow(syncState)
</script>

<style lang="scss" scoped>
.member-login-bar,
.member-user-bar {
  margin: 0 32rpx;
}

.member-login-bar {
  min-height: 88rpx;
  padding: 16rpx 24rpx;
  box-sizing: border-box;
  border-radius: 999rpx;
  background: #ecfdf5;
  border: 1rpx solid #bbf7d0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.member-login-bar__text {
  flex: 1;
  min-width: 0;
  font-size: 26rpx;
  font-weight: 700;
  color: #166534;
}

.member-login-bar__btn {
  flex-shrink: 0;
  margin: 0;
  padding: 0 28rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 999rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 24rpx;
  font-weight: 900;
  border: none;
}

.member-login-bar__btn::after {
  border: none;
}

.member-login-bar__btn--hover {
  opacity: 0.92;
}

.member-user-bar {
  min-height: 88rpx;
  padding: 12rpx 24rpx;
  box-sizing: border-box;
  border-radius: 999rpx;
  background: #fff;
  border: 1rpx solid $ok-slate-100;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.member-user-bar__profile {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.member-user-bar__avatar-wrap {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  background: $ok-slate-100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.member-user-bar__avatar {
  width: 100%;
  height: 100%;
}

.member-user-bar__avatar-fallback {
  font-size: 28rpx;
  font-weight: 900;
  color: $ok-forest-green;
}

.member-user-bar__name {
  flex: 1;
  min-width: 0;
  font-size: 28rpx;
  font-weight: 800;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-user-bar__btn {
  flex-shrink: 0;
  margin: 0;
  padding: 0 28rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 999rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 24rpx;
  font-weight: 900;
  border: none;
}

.member-user-bar__btn::after {
  border: none;
}

.member-user-bar__btn--hover {
  opacity: 0.92;
}
</style>
