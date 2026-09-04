<script>
import { ensureMemberPhoneFromStoredToken } from '@/utils/wxMemberLogin.js'
import { tryShowMemberCouponReminder } from '@/utils/memberCouponReminder.js'
import { tryShowEntryPoster } from '@/utils/entryPoster.js'
import { enforceWxMiniUpdate } from '@/utils/wxMiniUpdate.js'
import { reLaunchIfCourierModePreferred } from '@/utils/api.js'
import { parseRetailSpuIdFromQuery } from '@/utils/retailSharePoster.js'

let skipNextAppShow = false

/** 太阳码扫码落到首页时，跳转到对应零售商品详情 */
function maybeOpenRetailShare(options) {
  const q = (options && options.query) || {}
  const path = String((options && options.path) || '')
  if (path.includes('retailProductDetail')) return
  const spuId = parseRetailSpuIdFromQuery(q)
  if (spuId < 1) return
  uni.reLaunch({
    url: `/packageOrder/pages/retailProductDetail/retailProductDetail?spu_id=${spuId}`,
  })
}

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
  onLaunch: function (options) {
    skipNextAppShow = true
    enforceWxMiniUpdate()
    if (reLaunchIfCourierModePreferred()) return
    maybeOpenRetailShare(options)
    const fromShare = parseRetailSpuIdFromQuery((options && options.query) || {}) >= 1
    if (!fromShare) void onMemberAppReady()
    console.log('App Launch')
  },
  onShow: function (options) {
    if (skipNextAppShow) {
      skipNextAppShow = false
      console.log('App Show')
      return
    }
    maybeOpenRetailShare(options)
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
