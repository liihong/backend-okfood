<script>
import { ensureMemberPhoneFromStoredToken } from '@/utils/wxMemberLogin.js'
import { tryShowMemberCouponReminder } from '@/utils/memberCouponReminder.js'
import { enforceWxMiniUpdate } from '@/utils/wxMiniUpdate.js'
import { reLaunchIfCourierModePreferred } from '@/utils/api.js'

async function onMemberAppReady() {
  try {
    await ensureMemberPhoneFromStoredToken()
    // 延迟弹出，避免与首屏加载抢占（微信端不支持 import() 动态加载）
    setTimeout(() => {
      void tryShowMemberCouponReminder()
    }, 800)
  } catch (e) {
    console.warn('[App] onMemberAppReady', e)
  }
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
