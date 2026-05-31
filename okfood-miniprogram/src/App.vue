<script>
import { ensureMemberPhoneFromStoredToken } from '@/utils/wxMemberLogin.js'
import { tryShowMemberCouponReminder } from '@/utils/memberCouponReminder.js'
import { enforceWxMiniUpdate } from '@/utils/wxMiniUpdate.js'
import { reLaunchIfCourierModePreferred } from '@/utils/api.js'

async function onMemberAppReady() {
  await ensureMemberPhoneFromStoredToken()
  // 略延迟，避免与首页/onLaunch 其它弹窗抢占
  setTimeout(() => {
    void tryShowMemberCouponReminder()
  }, 600)
}

export default {
  onLaunch: function () {
    enforceWxMiniUpdate()
    reLaunchIfCourierModePreferred()
    void onMemberAppReady()
    console.log('App Launch')
  },
  onShow: function () {
    console.log('App Show')
  },
  onHide: function () {
    console.log('App Hide')
  },
}
</script>

<style lang="scss">
page {
  background-color: #f8fafc;
  font-family: -apple-system, 'PingFang SC', sans-serif;
}
</style>
