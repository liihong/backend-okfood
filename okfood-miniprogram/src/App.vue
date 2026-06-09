<script>
import { ensureMemberPhoneFromStoredToken } from '@/utils/wxMemberLogin.js'
import { tryShowMemberCouponReminder } from '@/utils/memberCouponReminder.js'
import { tryShowEntryPoster } from '@/utils/entryPoster.js'
import { enforceWxMiniUpdate } from '@/utils/wxMiniUpdate.js'
import { reLaunchIfCourierModePreferred } from '@/utils/api.js'

let skipNextAppShow = false

async function onMemberAppReady() {
  try {
    await ensureMemberPhoneFromStoredToken()
    // 延迟弹出，避免与首屏加载抢占（微信端不支持 import() 动态加载）
    setTimeout(async () => {
      const shown = await tryShowEntryPoster()
      if (!shown) {
        void tryShowMemberCouponReminder()
      }
    }, 600)
  } catch (e) {
    console.warn('[App] onMemberAppReady', e)
  }
}

async function onAppShow() {
  if (reLaunchIfCourierModePreferred()) return
  setTimeout(() => {
    void tryShowEntryPoster()
  }, 400)
}

export default {
  onLaunch: function () {
    skipNextAppShow = true
    enforceWxMiniUpdate()
    reLaunchIfCourierModePreferred()
    void onMemberAppReady()
    console.log('App Launch')
  },
  onShow: function () {
    if (skipNextAppShow) {
      skipNextAppShow = false
      console.log('App Show')
      return
    }
    void onAppShow()
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
