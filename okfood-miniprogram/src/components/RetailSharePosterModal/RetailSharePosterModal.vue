<template>
  <view>
    <canvas
      type="2d"
      id="retailSharePosterCanvas"
      class="poster-canvas"
      :style="canvasStyle"
    />
    <view v-if="visible" class="mask" @tap="onMask">
      <view class="panel" @tap.stop>
        <text class="panel__title">商品分享海报</text>
        <view class="preview-wrap">
          <image
            v-if="previewPath"
            class="preview"
            :src="previewPath"
            mode="widthFix"
            show-menu-by-longpress
          />
          <view v-else class="preview preview--loading">
            <text>{{ loadingText }}</text>
          </view>
        </view>
        <button
          class="btn btn--primary"
          type="default"
          hover-class="none"
          :disabled="!previewPath || saving"
          @tap="onSave"
        >
          {{ saving ? '保存中…' : '保存到相册' }}
        </button>
        <view class="btn btn--ghost" @tap="onClose">取消</view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, getCurrentInstance, nextTick, ref, watch } from 'vue'
import { showOkAlert } from '@/utils/okAlert.js'
import {
  POSTER_HEIGHT,
  POSTER_WIDTH,
  loadRetailSharePosterAssets,
  renderRetailSharePoster,
  savePosterToAlbum,
} from '@/utils/retailSharePoster.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  spuId: { type: Number, default: 0 },
  priceYuan: { type: [String, Number], default: '' },
  coverUrl: { type: String, default: '' },
})

const emit = defineEmits(['close'])

const instance = getCurrentInstance()
const previewPath = ref('')
const generating = ref(false)
const saving = ref(false)
const loadingText = ref('正在生成海报…')

const canvasStyle = computed(() => ({
  width: `${POSTER_WIDTH}px`,
  height: `${POSTER_HEIGHT}px`,
}))

function onClose() {
  emit('close')
}

function onMask() {
  if (generating.value) return
  onClose()
}

function getCanvasNode() {
  return new Promise((resolve, reject) => {
    const proxy = instance && instance.proxy
    const q = uni.createSelectorQuery()
    const scoped = proxy ? q.in(proxy) : q
    scoped
      .select('#retailSharePosterCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        const canvas = res && res[0] && res[0].node
        if (!canvas) {
          reject(new Error('画布未就绪'))
          return
        }
        resolve(canvas)
      })
  })
}

function wait(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

async function generate() {
  const id = Number(props.spuId)
  if (!Number.isFinite(id) || id < 1) {
    uni.showToast({ title: '商品无效', icon: 'none' })
    onClose()
    return
  }
  generating.value = true
  previewPath.value = ''
  loadingText.value = '正在生成海报…'
  try {
    const assets = await loadRetailSharePosterAssets(id, {
      priceYuan: props.priceYuan,
      coverUrl: props.coverUrl,
    })
    loadingText.value = '正在绘制…'
    await nextTick()
    await wait(80)
    let canvas = null
    let lastErr = null
    for (let i = 0; i < 3; i += 1) {
      try {
        canvas = await getCanvasNode()
        break
      } catch (e) {
        lastErr = e
        await wait(80)
      }
    }
    if (!canvas) throw lastErr || new Error('画布未就绪')
    previewPath.value = await renderRetailSharePoster(canvas, assets)
  } catch (e) {
    const msg = e && e.message ? String(e.message) : '生成海报失败'
    uni.showToast({ title: msg.slice(0, 20), icon: 'none' })
    onClose()
  } finally {
    generating.value = false
  }
}

async function onSave() {
  if (!previewPath.value || saving.value) return
  saving.value = true
  try {
    await savePosterToAlbum(previewPath.value)
    uni.showToast({ title: '已保存到相册', icon: 'success' })
  } catch (err) {
    const msg = String((err && err.errMsg) || (err && err.message) || '')
    const needAuth = /auth|authorize|permission|deny/i.test(msg)
    if (needAuth) {
      const ret = await showOkAlert({
        title: '需要相册权限',
        content: '请允许保存图片到相册，以便发朋友圈',
        confirmText: '去设置',
        showCancel: true,
      })
      if (ret && ret.confirm) uni.openSetting()
    } else {
      uni.showToast({ title: '保存失败', icon: 'none' })
    }
  } finally {
    saving.value = false
  }
}

watch(
  () => props.visible,
  (on) => {
    if (on) {
      void generate()
      return
    }
    previewPath.value = ''
    generating.value = false
    saving.value = false
  },
)
</script>

<style lang="scss" scoped>
.mask {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.poster-canvas {
  position: fixed;
  left: -9999px;
  top: 0;
  pointer-events: none;
}
.panel {
  width: 100%;
  max-height: 88vh;
  background: #fff;
  border-radius: 20px 20px 0 0;
  padding: 16px 16px calc(16px + env(safe-area-inset-bottom));
  box-sizing: border-box;
}
.panel__title {
  display: block;
  text-align: center;
  font-size: 16px;
  font-weight: 650;
  color: #0f172a;
  margin-bottom: 12px;
}
.preview-wrap {
  max-height: 56vh;
  overflow: hidden;
  border-radius: 12px;
  background: #f8fafc;
}
.preview {
  width: 100%;
  display: block;
  border-radius: 12px;
}
.preview--loading {
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-size: 14px;
}
.btn {
  margin-top: 12px;
  height: 44px;
  line-height: 44px;
  border-radius: 22px;
  text-align: center;
  font-size: 15px;
}
.btn--primary {
  background: #0d5c46;
  color: #fff;
  border: none;
}
.btn--primary[disabled] {
  opacity: 0.45;
}
.btn--ghost {
  color: #64748b;
}
.btn::after {
  border: none;
}
</style>
