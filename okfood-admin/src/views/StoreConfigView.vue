<script setup>
import { ref, onMounted } from 'vue'
import { Store } from 'lucide-vue-next'
import {
  apiJson,
  apiForm,
  adminAccessToken,
  handleAdminLogout,
  dishImageDisplayUrl,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import StoreLocationPicker from '../components/StoreLocationPicker.vue'

const loading = ref(false)
const saving = ref(false)
const logoUploading = ref(false)
const fileInput = ref(null)

const form = ref({
  store_name: '',
  store_logo_url: '',
  store_lng: '',
  store_lat: '',
})

async function loadConfig() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const d = await apiJson('/api/admin/store-config', {}, { auth: true })
    form.value.store_name = d?.store_name != null ? String(d.store_name) : ''
    form.value.store_logo_url = d?.store_logo_url != null ? String(d.store_logo_url) : ''
    form.value.store_lng =
      d?.store_lng != null && Number.isFinite(Number(d.store_lng)) ? String(d.store_lng) : ''
    form.value.store_lat =
      d?.store_lat != null && Number.isFinite(Number(d.store_lat)) ? String(d.store_lat) : ''
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (!adminAccessToken.value || saving.value) return
  const payload = {}
  const name = form.value.store_name.trim()
  payload.store_name = name || null
  const logo = form.value.store_logo_url.trim()
  payload.store_logo_url = logo || null

  const ln = form.value.store_lng.trim()
  const lt = form.value.store_lat.trim()
  if (ln !== '' && lt !== '') {
    const lng = Number(ln)
    const lat = Number(lt)
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
      showToast('经纬度必须为有效数字', 'error')
      return
    }
    payload.store_lng = lng
    payload.store_lat = lat
  } else if (ln === '' && lt === '') {
    payload.store_lng = null
    payload.store_lat = null
  } else {
    showToast('经度与纬度请成对填写，或同时留空以清除门店坐标', 'error')
    return
  }

  saving.value = true
  try {
    await apiJson(
      '/api/admin/store-config',
      {
        method: 'PUT',
        body: JSON.stringify(payload),
      },
      { auth: true },
    )
    showToast('已保存', 'success')
    await loadConfig()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

function triggerLogoPick() {
  if (logoUploading.value) return
  fileInput.value?.click()
}

async function onLogoFileChange(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file || !file.type.startsWith('image/')) return
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  logoUploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const data = await apiForm('/api/admin/upload', fd, { auth: true })
    const url = data && typeof data.url === 'string' ? data.url.trim() : ''
    if (url) {
      form.value.store_logo_url = url
      showToast('Logo 已上传', 'success')
    } else {
      showToast('上传成功但未返回地址', 'error')
    }
  } catch (err) {
    const status = err && typeof err.status === 'number' ? err.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(err instanceof Error ? err.message : '上传失败', 'error')
  } finally {
    logoUploading.value = false
  }
}

const logoPreviewUrl = () => dishImageDisplayUrl(form.value.store_logo_url)

function onMapWarn(msg) {
  showToast(typeof msg === 'string' ? msg : '地图提示', 'error')
}

onMounted(() => {
  void loadConfig()
})
</script>

<template>
  <section class="tab-content animate-up store-config-page">
    <div class="sc-head">
      <Store :size="22" class="sc-head-icon" aria-hidden="true" />
      <div>
        <h2 class="sc-title">门店基础信息</h2>
        <p class="sc-desc">
          请优先用下方地图<strong>搜索或点选</strong>门店位置（与高德一致，自动为 GCJ-02）。保存后营业概览以门店为中心；骑手端任务按<strong>离该点直线距离</strong>由近到远排序。
        </p>
      </div>
    </div>

    <p v-if="loading" class="sc-muted">加载中…</p>

    <div v-else class="sc-card">
      <div class="sc-field">
        <label class="sc-label" for="sc-name">门店名称</label>
        <input id="sc-name" v-model="form.store_name" type="text" class="sc-input" maxlength="128" />
      </div>

      <div class="sc-field">
        <span class="sc-label">门店 Logo</span>
        <input ref="fileInput" type="file" accept="image/*" class="sc-file" @change="onLogoFileChange" />
        <div class="sc-logo-row">
          <div class="sc-logo-preview-wrap">
            <img v-if="logoPreviewUrl()" :src="logoPreviewUrl()" alt="" class="sc-logo-preview" />
            <span v-else class="sc-logo-placeholder">未设置</span>
          </div>
          <button type="button" class="sc-btn-secondary" :disabled="logoUploading" @click="triggerLogoPick">
            {{ logoUploading ? '上传中…' : '上传图片' }}
          </button>
        </div>
        <input v-model="form.store_logo_url" type="text" class="sc-input sc-input--mono" placeholder="或直接粘贴图片 URL" />
      </div>

      <div class="sc-field">
        <span class="sc-label">地图选点（高德搜索 / 点击地图 / 拖动标记）</span>
        <StoreLocationPicker
          v-model:lng-str="form.store_lng"
          v-model:lat-str="form.store_lat"
          @warn="onMapWarn"
        />
      </div>

      <div class="sc-coord-grid">
        <div class="sc-field">
          <label class="sc-label" for="sc-lng">经度 lng（可微调）</label>
          <input id="sc-lng" v-model="form.store_lng" type="text" class="sc-input sc-input--mono" placeholder="例：113.9268" />
        </div>
        <div class="sc-field">
          <label class="sc-label" for="sc-lat">纬度 lat（可微调）</label>
          <input id="sc-lat" v-model="form.store_lat" type="text" class="sc-input sc-input--mono" placeholder="例：35.303" />
        </div>
      </div>

      <div class="sc-actions">
        <button type="button" class="sc-btn-primary" :disabled="saving" @click="saveConfig">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.store-config-page {
  max-width: 52rem;
}
.sc-head {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  margin-bottom: 1.25rem;
}
.sc-head-icon {
  color: #0e5a44;
  flex-shrink: 0;
  margin-top: 2px;
}
.sc-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 800;
  color: #0f172a;
}
.sc-desc {
  margin: 0.35rem 0 0;
  font-size: 13px;
  line-height: 1.5;
  color: #64748b;
}
.sc-muted {
  color: #64748b;
  font-size: 14px;
}
.sc-card {
  padding: 1.25rem 1.35rem;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 1rem;
}
.sc-field {
  margin-bottom: 1.1rem;
}
.sc-label {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 0.35rem;
}
.sc-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.55rem 0.65rem;
  font-size: 14px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-family: inherit;
}
.sc-input--mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}
.sc-file {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
.sc-logo-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}
.sc-logo-preview-wrap {
  width: 72px;
  height: 72px;
  border-radius: 12px;
  border: 1px dashed #cbd5e1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #f8fafc;
}
.sc-logo-preview {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.sc-logo-placeholder {
  font-size: 12px;
  color: #94a3b8;
}
.sc-btn-secondary {
  padding: 0.45rem 0.85rem;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  font-family: inherit;
}
.sc-btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.sc-coord-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
@media (max-width: 640px) {
  .sc-coord-grid {
    grid-template-columns: 1fr;
  }
}
.sc-actions {
  margin-top: 0.5rem;
}
.sc-btn-primary {
  padding: 0.55rem 1.25rem;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  background: #0e5a44;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-family: inherit;
}
.sc-btn-primary:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
.sc-btn-primary:hover:not(:disabled) {
  background: #0c4d3a;
}
</style>
