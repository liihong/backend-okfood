<script setup>
defineOptions({ name: 'StoreConfigView' })
import { ref, onMounted, computed } from 'vue'
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
const form = ref({
  store_name: '',
  store_contact_phone: '',
  store_logo_url: '',
  store_lng: '',
  store_lat: '',
  /** 每日 07:00（上海）自动顺丰推送当日配送单 */
  sf_nightly_auto_push_enabled: false,
  /** 单次点餐推顺丰：顺丰侧店铺编号，与大表推单租户 shop 区分 */
  sf_retail_push_shop_id: '',
  /** 1 / 2 / 空字符串表示跟随租户 */
  sf_retail_push_shop_type: '',
  uu_open_app_id: '',
  uu_open_app_key_input: '',
  uu_clear_app_key: false,
  uu_open_app_key_set: false,
  wechat_pay_ssl_cert_path: '',
  wechat_pay_ssl_key_path: '',
  courier_delivery_base_yuan: '',
  courier_delivery_extra_per_unit_yuan: '',
})

async function loadConfig() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const d = await apiJson('/api/admin/store-config', {}, { auth: true })
    form.value.store_name = d?.store_name != null ? String(d.store_name) : ''
    form.value.store_contact_phone =
      d?.store_contact_phone != null ? String(d.store_contact_phone).trim() : ''
    form.value.store_logo_url = d?.store_logo_url != null ? String(d.store_logo_url) : ''
    form.value.store_lng =
      d?.store_lng != null && Number.isFinite(Number(d.store_lng)) ? String(d.store_lng) : ''
    form.value.store_lat =
      d?.store_lat != null && Number.isFinite(Number(d.store_lat)) ? String(d.store_lat) : ''
    const fmtMoney = (v) => (v != null && v !== '' && Number.isFinite(Number(v)) ? String(Number(v)) : '')
    form.value.courier_delivery_base_yuan = fmtMoney(d?.courier_delivery_base_yuan)
    form.value.courier_delivery_extra_per_unit_yuan = fmtMoney(d?.courier_delivery_extra_per_unit_yuan)
    form.value.sf_nightly_auto_push_enabled = d?.sf_nightly_auto_push_enabled === true
    form.value.sf_retail_push_shop_id =
      d?.sf_retail_push_shop_id != null ? String(d.sf_retail_push_shop_id).trim() : ''
    form.value.sf_retail_push_shop_type =
      d?.sf_retail_push_shop_type != null ? String(d.sf_retail_push_shop_type) : ''
    form.value.uu_open_app_id = d?.uu_open_app_id != null ? String(d.uu_open_app_id).trim() : ''
    form.value.uu_open_app_key_input = ''
    form.value.uu_clear_app_key = false
    form.value.uu_open_app_key_set = d?.uu_open_app_key_set === true
    form.value.wechat_pay_ssl_cert_path =
      d?.wechat_pay_ssl_cert_path != null ? String(d.wechat_pay_ssl_cert_path).trim() : ''
    form.value.wechat_pay_ssl_key_path =
      d?.wechat_pay_ssl_key_path != null ? String(d.wechat_pay_ssl_key_path).trim() : ''
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
  payload.store_contact_phone = form.value.store_contact_phone.trim() || null
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

  const parseMoney = (raw, label) => {
    const t = String(raw ?? '').trim()
    if (t === '') {
      showToast(`请填写${label}`, 'error')
      return null
    }
    const n = Number(t)
    if (!Number.isFinite(n) || n < 0) {
      showToast(`${label}须为非负数字`, 'error')
      return null
    }
    return n
  }
  const base = parseMoney(form.value.courier_delivery_base_yuan, '配送费首份基础价')
  if (base === null) return
  const extra = parseMoney(form.value.courier_delivery_extra_per_unit_yuan, '配送费每多一份加价')
  if (extra === null) return
  payload.courier_delivery_base_yuan = base
  payload.courier_delivery_extra_per_unit_yuan = extra
  payload.sf_nightly_auto_push_enabled = form.value.sf_nightly_auto_push_enabled === true
  payload.sf_retail_push_shop_id = form.value.sf_retail_push_shop_id.trim() || null
  const rst = String(form.value.sf_retail_push_shop_type ?? '').trim()
  if (rst === '') payload.sf_retail_push_shop_type = null
  else {
    const n = Number(rst)
    if (!Number.isFinite(n)) {
      showToast('零售顺丰 shop_type 须为数字或留空', 'error')
      return
    }
    payload.sf_retail_push_shop_type = n
  }
  payload.uu_open_app_id = form.value.uu_open_app_id.trim() || null
  if (form.value.uu_clear_app_key) {
    payload.uu_open_app_key = ''
  } else {
    const uk = form.value.uu_open_app_key_input.trim()
    if (uk) payload.uu_open_app_key = uk
  }
  payload.wechat_pay_ssl_cert_path = form.value.wechat_pay_ssl_cert_path.trim() || null
  payload.wechat_pay_ssl_key_path = form.value.wechat_pay_ssl_key_path.trim() || null

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

const logoUploadKey = ref(0)

async function onLogoUploadChange(uploadFile) {
  const file = uploadFile?.raw
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
    logoUploadKey.value += 1
  }
}

const logoPreviewUrl = () => dishImageDisplayUrl(form.value.store_logo_url)

function onMapWarn(msg) {
  showToast(typeof msg === 'string' ? msg : '地图提示', 'error')
}

const locationDialogVisible = ref(false)

const locationSummaryText = computed(() => {
  const ln = String(form.value.store_lng ?? '').trim()
  const lt = String(form.value.store_lat ?? '').trim()
  if (ln && lt) return `经度 ${ln}，纬度 ${lt}`
  return ''
})

function closeLocationDialog() {
  locationDialogVisible.value = false
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
        <h2 class="sc-title">门店与全局计价</h2>
        <p class="sc-desc">
          请通过「<strong>地图选点</strong>」在弹窗内用高德<strong>搜索或点选</strong>门店位置（自动为 GCJ-02）。保存后营业概览以门店为中心；骑手端任务按<strong>离该点直线距离</strong>由近到远排序。门店基础与配送相关参数保存在当前门店配置中，保存后立即对骑手结费、顺丰推单与小程序展示生效。
        </p>
      </div>
    </div>

    <p v-if="loading" class="sc-muted">加载中…</p>

    <div v-else class="sc-blocks">
      <el-card class="sc-el-card" shadow="never">
        <template #header>
          <span class="sc-card-title">门店基础信息</span>
        </template>
        <div class="sc-field">
          <label class="sc-label" for="sc-name">门店名称</label>
          <el-input id="sc-name" v-model="form.store_name" class="sc-input-el" maxlength="128" clearable />
        </div>

        <div class="sc-field">
          <label class="sc-label" for="sc-contact-phone">商家电话</label>
          <el-input
            id="sc-contact-phone"
            v-model="form.store_contact_phone"
            class="sc-input-el"
            maxlength="20"
            clearable
            placeholder="小程序订单详情「联系商家」将直接拨打此号码"
          />
          <p class="sc-hint sc-hint--tight">供餐咨询、取消订单等；留空则小程序不展示拨打能力。</p>
        </div>

        <div class="sc-field sc-field--last">
          <span class="sc-label">门店 Logo</span>
          <div class="sc-logo-row">
            <div class="sc-logo-preview-wrap">
              <img v-if="logoPreviewUrl()" :src="logoPreviewUrl()" alt="" class="sc-logo-preview" />
              <span v-else class="sc-logo-placeholder">未设置</span>
            </div>
            <el-upload
              :key="logoUploadKey"
              :show-file-list="false"
              :auto-upload="false"
              accept="image/*"
              @change="onLogoUploadChange"
            >
              <el-button type="default" :disabled="logoUploading">{{
                logoUploading ? '上传中…' : '上传图片'
              }}</el-button>
            </el-upload>
          </div>
          <el-input
            v-model="form.store_logo_url"
            class="sc-input-el sc-input-el--mono"
            placeholder="或直接粘贴图片 URL"
            clearable
          />
        </div>
      </el-card>

      <el-card class="sc-el-card" shadow="never">
        <template #header>
          <span class="sc-card-title">门店位置</span>
        </template>
        <p class="sc-hint sc-hint--card">
          使用高德地图搜索、点击或拖动标记选点（GCJ-02）。弹窗内可微调经纬度；保存设置仍须点击页面底部「保存」。
        </p>
        <div class="sc-location-bar">
          <div class="sc-location-summary">
            <span v-if="locationSummaryText" class="sc-coord-line">{{ locationSummaryText }}</span>
            <span v-else class="sc-location-empty">尚未设置坐标</span>
          </div>
          <el-button type="primary" @click="locationDialogVisible = true"> 地图选点 </el-button>
        </div>
      </el-card>

      <el-card class="sc-el-card" shadow="never">
        <template #header>
          <span class="sc-card-title">配送信息管理</span>
        </template>
        <div class="sc-field sc-switch-row sc-switch-row--card">
          <div class="sc-switch-text">
            <span class="sc-label sc-label--inline">顺丰自动推单</span>
            <p class="sc-hint sc-hint--tight">
              开启后系统于每日<strong>07:00（上海时间）</strong>自动将<strong>当日</strong>智能配送大表（订阅合并）订单推送至顺丰同城；<strong>单次零售订单</strong>请在订单管理页面手动推单。关闭后不执行定时任务，请在配送大表<strong>手动推单</strong>。
            </p>
          </div>
          <el-switch v-model="form.sf_nightly_auto_push_enabled" size="large" />
        </div>
        <el-divider class="sc-inner-divider" content-position="left">骑手配送费（元）</el-divider>
        <p class="sc-hint sc-hint--card">确认送达时写入骑手待结算：首份基础价 +（份数 − 1）× 每多一份加价。</p>
        <div class="sc-coord-grid">
          <div class="sc-field sc-field--last-in-grid">
            <label class="sc-label" for="sc-fee-base">首份基础价</label>
            <el-input
              id="sc-fee-base"
              v-model="form.courier_delivery_base_yuan"
              class="sc-input-el sc-input-el--mono"
              placeholder="例：4"
              clearable
            />
          </div>
          <div class="sc-field sc-field--last-in-grid">
            <label class="sc-label" for="sc-fee-extra">同地址每多一份加价</label>
            <el-input
              id="sc-fee-extra"
              v-model="form.courier_delivery_extra_per_unit_yuan"
              class="sc-input-el sc-input-el--mono"
              placeholder="例：1"
              clearable
            />
          </div>
        </div>
      </el-card>

      <el-card class="sc-el-card" shadow="never">
        <template #header>
          <span class="sc-card-title">单次点餐 / 零售 · 顺丰与 UU</span>
        </template>
        <p class="sc-hint sc-hint--card">
          <strong>零售推顺丰店铺ID</strong>仅用于订单管理里「推送到顺丰」；开发者 ID、密钥、取件电话/地址仍使用<strong>租户对接</strong>或 .env（与智能配送大表手动/夜间推单使用的「租户顺丰店铺编号」可填不同值，例如
          <code class="sc-code">6284388701377</code>）。
        </p>
        <div class="sc-coord-grid">
          <div class="sc-field">
            <label class="sc-label" for="sc-sf-retail-shop">零售推顺丰店铺ID</label>
            <el-input
              id="sc-sf-retail-shop"
              v-model="form.sf_retail_push_shop_id"
              class="sc-input-el sc-input-el--mono"
              maxlength="64"
              clearable
              placeholder="顺丰开放平台店铺编号，与大表推单 shop 独立"
            />
          </div>
          <div class="sc-field">
            <label class="sc-label" for="sc-sf-retail-type">shop_type（可选）</label>
            <el-select
              id="sc-sf-retail-type"
              v-model="form.sf_retail_push_shop_type"
              class="sc-input-el"
              clearable
              placeholder="留空则与租户/全局一致"
              style="width: 100%"
            >
              <el-option label="1 · 顺丰门店编号" value="1" />
              <el-option label="2 · 接入方自建店" value="2" />
            </el-select>
          </div>
        </div>

        <p class="sc-hint sc-hint--tight sc-hint--spaced">
          <strong>UU 跑腿</strong>发单接口预留字段（保存后可入库；点击订单「推 UU」将提示待对接）。
        </p>
        <div class="sc-coord-grid">
          <div class="sc-field">
            <label class="sc-label" for="sc-uu-app">UU AppId（预留）</label>
            <el-input id="sc-uu-app" v-model="form.uu_open_app_id" maxlength="64" clearable />
          </div>
          <div class="sc-field">
            <label class="sc-label" for="sc-uu-key">UU AppKey（预留）</label>
            <el-input
              id="sc-uu-key"
              v-model="form.uu_open_app_key_input"
              type="password"
              show-password
              maxlength="255"
              clearable
              :placeholder="form.uu_open_app_key_set ? '已保存，留空不改；或填写新密钥' : '可选填写'"
            />
          </div>
        </div>
        <div class="sc-field sc-checkbox-row sc-field--last">
          <el-checkbox v-model="form.uu_clear_app_key">清除已保存的 UU AppKey</el-checkbox>
        </div>
      </el-card>

      <el-card class="sc-el-card" shadow="never">
        <template #header>
          <span class="sc-card-title">微信支付 · 退款证书（本门店）</span>
        </template>
        <p class="sc-hint sc-hint--card">
          管理端「微信原路退款」使用微信
          <strong>secapi 退款</strong> 接口，须商户平台下发的 <code class="sc-code">apiclient_cert.pem</code> 与
          <code class="sc-code">apiclient_key.pem</code>。请填写<strong>服务器可读的本地路径</strong>（绝对路径或相对进程工作目录）。
          <strong>优先级</strong>：本门店填写 &gt; 租户「对接配置」中的默认路径 &gt; 服务器环境变量
          <code class="sc-code">WECHAT_PAY_SSL_*</code>。同一租户下多门店若共用同一商户号，也可仅在租户对接中配置一次。
        </p>
        <div class="sc-field">
          <label class="sc-label" for="sc-wx-cert">apiclient_cert.pem 路径</label>
          <el-input
            id="sc-wx-cert"
            v-model="form.wechat_pay_ssl_cert_path"
            class="sc-input-el sc-input-el--mono"
            maxlength="512"
            clearable
            placeholder="例：E:/certs/apiclient_cert.pem"
          />
        </div>
        <div class="sc-field sc-field--last">
          <label class="sc-label" for="sc-wx-key">apiclient_key.pem 路径</label>
          <el-input
            id="sc-wx-key"
            v-model="form.wechat_pay_ssl_key_path"
            class="sc-input-el sc-input-el--mono"
            maxlength="512"
            clearable
            placeholder="例：E:/certs/apiclient_key.pem"
          />
        </div>
      </el-card>

      <div class="sc-actions">
        <button type="button" class="sc-btn-primary" :disabled="saving" @click="saveConfig">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>

    <el-dialog
      v-model="locationDialogVisible"
      title="地图选点（高德搜索 / 点击地图 / 拖动标记）"
      width="min(92vw, 880px)"
      top="5vh"
      destroy-on-close
      class="sc-location-dialog"
    >
      <div v-if="locationDialogVisible" class="sc-location-dialog-body">
        <StoreLocationPicker
          class="sc-location-picker-dialog"
          v-model:lng-str="form.store_lng"
          v-model:lat-str="form.store_lat"
          @warn="onMapWarn"
        />
        <div class="sc-coord-grid">
          <div class="sc-field sc-field--tight">
            <label class="sc-label" for="sc-lng">经度 lng（可微调）</label>
            <el-input
              id="sc-lng"
              v-model="form.store_lng"
              class="sc-input-el sc-input-el--mono"
              placeholder="例：113.9268"
              clearable
            />
          </div>
          <div class="sc-field sc-field--tight">
            <label class="sc-label" for="sc-lat">纬度 lat（可微调）</label>
            <el-input
              id="sc-lat"
              v-model="form.store_lat"
              class="sc-input-el sc-input-el--mono"
              placeholder="例：35.303"
              clearable
            />
          </div>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="closeLocationDialog">完成</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.store-config-page {
  max-width: min(72rem, 100%);
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
.sc-code {
  font-size: 12px;
  padding: 0.1rem 0.35rem;
  background: #f1f5f9;
  border-radius: 4px;
}
.sc-hint {
  margin: 0 0 0.75rem;
  font-size: 12px;
  line-height: 1.45;
  color: #64748b;
}
.sc-muted {
  color: #64748b;
  font-size: 14px;
}
.sc-blocks {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  align-items: stretch;
}
.sc-el-card {
  margin-bottom: 0;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.sc-el-card :deep(.el-card__header) {
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid #f1f5f9;
}
.sc-card-title {
  font-size: 0.95rem;
  font-weight: 800;
  color: #0f172a;
}
.sc-el-card :deep(.el-card__body) {
  padding: 1.15rem 1.25rem 1.25rem;
  flex: 1;
}
.sc-hint--card {
  margin-top: 0;
}
.sc-hint--spaced {
  margin-top: 0.75rem;
}
.sc-inner-divider {
  margin: 0.35rem 0 0.5rem;
}
.sc-inner-divider :deep(.el-divider__text) {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}
.sc-field--last-in-grid {
  margin-bottom: 0;
}
.sc-location-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.sc-location-summary {
  flex: 1;
  min-width: 200px;
}
.sc-coord-line {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: #0f172a;
}
.sc-location-empty {
  font-size: 13px;
  color: #94a3b8;
}
.sc-field {
  margin-bottom: 1.1rem;
}
.sc-field--tight {
  margin-bottom: 0.75rem;
}
.sc-field--last {
  margin-bottom: 0;
}
.sc-switch-row--card {
  border: none;
  padding: 0;
  margin-bottom: 0;
}
.sc-location-picker-dialog :deep(.slp-map) {
  height: min(420px, 48vh);
  min-height: 260px;
}
.sc-label {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 0.35rem;
}
.sc-label--inline {
  margin-bottom: 0.25rem;
}
.sc-switch-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem 0;
  margin-bottom: 0.5rem;
  border-top: 1px solid #f1f5f9;
  border-bottom: 1px solid #f1f5f9;
}
.sc-switch-text {
  flex: 1;
  min-width: 220px;
}
.sc-hint--tight {
  margin: 0.25rem 0 0;
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
.sc-input-el {
  width: 100%;
}
.sc-input-el--mono :deep(.el-input__inner) {
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
@media (max-width: 900px) {
  .sc-blocks {
    grid-template-columns: 1fr;
  }
}
.sc-actions {
  grid-column: 1 / -1;
  margin-top: 0.35rem;
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
