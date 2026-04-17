<script>
import { ensureMemberPhoneFromStoredToken } from '@/utils/wxMemberLogin.js'
import { reLaunchIfCourierModePreferred } from '@/utils/api.js'

export default {
  onLaunch: function () {
    void ensureMemberPhoneFromStoredToken()
    reLaunchIfCourierModePreferred()
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
