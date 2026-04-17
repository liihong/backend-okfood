<template>
  <view class="map-pick-shim" />
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'

/** 历史路由：地图选点曾独立成页；现合并到 address，旧入口与缓存 app.json 仍可能指向本页 */
function buildQuery(options) {
  if (!options || typeof options !== 'object') return ''
  const parts = []
  for (const k of Object.keys(options)) {
    const v = options[k]
    if (v == null || v === '') continue
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  }
  return parts.length ? `?${parts.join('&')}` : ''
}

onLoad((options) => {
  const qs = buildQuery(options)
  uni.redirectTo({
    url: `/packageUser/pages/address/address${qs}`,
    fail() {
      uni.reLaunch({ url: `/packageUser/pages/address/address${qs}` })
    },
  })
})
</script>

<style lang="scss" scoped>
.map-pick-shim {
  min-height: 100vh;
  background: #ffffff;
}
</style>
