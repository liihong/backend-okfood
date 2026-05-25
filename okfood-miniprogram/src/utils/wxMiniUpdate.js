/**
 * 微信小程序强制更新：新版本下载完成后弹窗并重启，不可取消。
 * 配合公众平台「设置 → 版本设置 → 小程序最低可用版本」使用效果最佳。
 */
export function enforceWxMiniUpdate() {
  // #ifdef MP-WEIXIN
  if (typeof uni.getUpdateManager !== 'function') return

  const updateManager = uni.getUpdateManager()
  let downloading = false

  updateManager.onCheckForUpdate((res) => {
    if (!res.hasUpdate) return
    downloading = true
    uni.showLoading({ title: '正在下载新版本...', mask: true })
  })

  updateManager.onUpdateReady(() => {
    if (downloading) {
      uni.hideLoading()
      downloading = false
    }
    uni.showModal({
      title: '更新提示',
      content: '新版本已准备好，请重启小程序以继续使用',
      showCancel: false,
      confirmText: '立即重启',
      success() {
        updateManager.applyUpdate()
      },
    })
  })

  updateManager.onUpdateFailed(() => {
    if (downloading) {
      uni.hideLoading()
      downloading = false
    }
    uni.showModal({
      title: '更新失败',
      content:
        '新版本下载失败，请检查网络后重新打开小程序；若仍失败，请删除小程序后重新搜索打开',
      showCancel: false,
      confirmText: '我知道了',
    })
  })
  // #endif
}
