<script setup>
defineOptions({ name: 'StoreConfigView' })
import { ref, onMounted, computed } from 'vue'
import {
  apiJson,
  apiForm,
  adminAccessToken,
  handleAdminLogout,
  dishImageDisplayUrl,
  syncAdminStoreBrandingFromPayload,
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
  /** 每日 08:50（上海）自动顺丰推送当日配送单 */
  sf_nightly_auto_push_enabled: false,
  /** 同地址不同会员是否合并为一单推顺丰；默认否（按会员拆单） */
  sf_merge_same_address_push: false,
  /** 单次点餐推顺丰：顺丰侧店铺编号，与大表推单租户 shop 区分 */
  sf_retail_push_shop_id: '',
  /** 1 / 2 / 空字符串表示跟随租户 */
  sf_retail_push_shop_type: '',
  uu_open_app_id: '',
  uu_open_app_key_input: '',
  uu_clear_app_key: false,
  uu_open_app_key_set: false,
  douyin_poi_id: '',
  douyin_account_id: '',
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
    form.value.sf_merge_same_address_push = d?.sf_merge_same_address_push === true
    form.value.sf_retail_push_shop_id =
      d?.sf_retail_push_shop_id != null ? String(d.sf_retail_push_shop_id).trim() : ''
    form.value.sf_retail_push_shop_type =
      d?.sf_retail_push_shop_type != null ? String(d.sf_retail_push_shop_type) : ''
    form.value.uu_open_app_id = d?.uu_open_app_id != null ? String(d.uu_open_app_id).trim() : ''
    form.value.uu_open_app_key_input = ''
    form.value.uu_clear_app_key = false
    form.value.uu_open_app_key_set = d?.uu_open_app_key_set === true
    form.value.douyin_poi_id = d?.douyin_poi_id != null ? String(d.douyin_poi_id).trim() : ''
    form.value.douyin_account_id =
      d?.douyin_account_id != null ? String(d.douyin_account_id).trim() : ''
    syncAdminStoreBrandingFromPayload({
      store_name: form.value.store_name,
      store_logo_url: form.value.store_logo_url,
    })
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
  payload.sf_merge_same_address_push = form.value.sf_merge_same_address_push === true
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
  payload.douyin_poi_id = form.value.douyin_poi_id.trim() || null
  payload.douyin_account_id = form.value.douyin_account_id.trim() || null

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
    <header class="sc-page-head">
      <div class="sc-page-head__copy">
        <p class="sc-kicker">系统管理</p>
        <h1 class="sc-title">门店配置</h1>
        <p class="sc-intro">
          名称、电话、Logo 与位置在基础信息里设置。位置用「地图选点」（GCJ-02）。保存后营业概览以门店为中心，骑手任务按离该点直线距离排序。配送与核销参数保存后立即生效。
        </p>
      </div>
      <el-button
        class="sc-save"
        type="primary"
        round
        size="large"
        :loading="saving"
        :disabled="loading"
        @click="saveConfig"
      >
        {{ saving ? '保存中…' : '保存配置' }}
      </el-button>
    </header>

    <p v-if="loading" class="sc-muted">加载中…</p>

    <div v-else class="sc-blocks">
      <article class="sc-card sc-card--identity">
        <header class="sc-card__head">
          <span class="sc-card__title">门店基础信息</span>
          <span class="sc-card__hint">小程序展示与地图中心</span>
        </header>
        <div class="sc-pair">
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
        </div>

        <div class="sc-field">
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
              <el-button round :disabled="logoUploading">{{
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

        <div class="sc-field sc-field--last">
          <span class="sc-label">门店位置</span>
          <p class="sc-hint sc-hint--tight">
            使用高德地图搜索、点击或拖动标记选点（GCJ-02）。弹窗内可微调经纬度；保存设置仍须点击右上角「保存配置」。
          </p>
          <div class="sc-location-bar">
            <div class="sc-location-summary">
              <span v-if="locationSummaryText" class="sc-coord-line">{{ locationSummaryText }}</span>
              <span v-else class="sc-location-empty">尚未设置坐标</span>
            </div>
            <el-button type="primary" round @click="locationDialogVisible = true">地图选点</el-button>
          </div>
        </div>
      </article>

      <article class="sc-card">
        <header class="sc-card__head">
          <span class="sc-card__title">配送信息</span>
          <span class="sc-card__hint">推单与骑手结算</span>
        </header>
        <div class="sc-field sc-switch-row">
          <div class="sc-switch-text">
            <span class="sc-label sc-label--inline">顺丰自动推单</span>
            <p class="sc-hint sc-hint--tight">
              开启后系统于每日<strong>08:50（上海时间）</strong>自动将<strong>当日</strong>智能配送大表（订阅合并）订单推送至顺丰同城。主租户还会把当时已经下单、供餐日为当天的零售订单推到<strong>及时单账号</strong>（零售推顺丰店铺），并标为配送中；这次推单之后新下的零售订单，请在订单管理手动推单。关闭后不执行定时任务，请在配送大表<strong>手动推单</strong>。
            </p>
          </div>
          <el-switch v-model="form.sf_nightly_auto_push_enabled" size="large" />
        </div>
        <div class="sc-field sc-switch-row">
          <div class="sc-switch-text">
            <span class="sc-label sc-label--inline">同地址合并推送</span>
            <p class="sc-hint sc-hint--tight">
              开启后，<strong>同一配送地址</strong>的不同会员合并为 <strong>1</strong> 个顺丰订单、只扣 <strong>1</strong> 份配送费；关闭则一名会员一单（默认，不影响其它门店）。
            </p>
          </div>
          <el-switch v-model="form.sf_merge_same_address_push" size="large" />
        </div>
        <p class="sc-section-label">骑手配送费（元）</p>
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
      </article>

      <article class="sc-card">
        <header class="sc-card__head">
          <span class="sc-card__title">零售顺丰与 UU</span>
          <span class="sc-card__hint">单次点餐</span>
        </header>
        <p class="sc-hint sc-hint--card">
          <strong>零售推顺丰店铺ID</strong>用于订单管理「推送到顺丰」以及配送大表「推送及时单」；开发者 ID、密钥、取件电话/地址仍使用<strong>租户对接</strong>或 .env（与智能配送大表预约/夜间推单使用的「租户顺丰店铺编号」可填不同值，例如
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
      </article>

      <article class="sc-card sc-card--wide">
        <header class="sc-card__head">
          <span class="sc-card__title">抖音团购核销</span>
          <span class="sc-card__hint">来客门店</span>
        </header>
        <p class="sc-hint sc-hint--card">
          填写抖音来客门店 <strong>POI ID</strong>，小程序验券时将按此门店调用抖音核销接口。开放平台
          <code class="sc-code">client_key/secret</code> 请在租户「对接配置」的 extra_json 或环境变量中配置。
        </p>
        <div class="sc-coord-grid">
          <div class="sc-field">
            <label class="sc-label" for="sc-dy-poi">抖音 POI ID</label>
            <el-input
              id="sc-dy-poi"
              v-model="form.douyin_poi_id"
              class="sc-input-el sc-input-el--mono"
              maxlength="64"
              clearable
              placeholder="来客门店 POI"
            />
          </div>
          <div class="sc-field">
            <label class="sc-label" for="sc-dy-account">account_id（可选）</label>
            <el-input
              id="sc-dy-account"
              v-model="form.douyin_account_id"
              class="sc-input-el sc-input-el--mono"
              maxlength="64"
              clearable
            />
          </div>
        </div>
      </article>
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
        <el-button type="primary" round @click="closeLocationDialog">完成</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.store-config-page {
  max-width: min(72rem, 100%);
  color: #1d1f21;
}

.sc-page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.25rem;
  margin-bottom: 1.15rem;
}

.sc-page-head__copy {
  min-width: 0;
}

.sc-kicker {
  margin: 0 0 0.2rem;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--el-color-primary);
}

.sc-title {
  margin: 0;
  font-size: 1.65rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.15;
}

.sc-intro {
  margin: 0.45rem 0 0;
  max-width: 46rem;
  font-size: 13px;
  line-height: 1.55;
  color: #5c6670;
}

.sc-save {
  flex-shrink: 0;
  min-width: 7.5rem;
  font-weight: 800;
}

.sc-code {
  font-size: 12px;
  padding: 0.1rem 0.4rem;
  border-radius: 6px;
  background: color-mix(in srgb, var(--el-color-primary) 10%, #fff);
  color: var(--el-color-primary-dark-2);
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
  gap: 0.9rem;
  align-items: stretch;
}

.sc-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 1.05rem 1.15rem 1.15rem;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.82);
  background: rgba(255, 255, 255, 0.72);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 14px 36px rgba(25, 45, 55, 0.06);
  backdrop-filter: saturate(1.15) blur(14px);
  -webkit-backdrop-filter: saturate(1.15) blur(14px);
}

.sc-card--identity,
.sc-card--wide {
  grid-column: 1 / -1;
}

.sc-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.sc-card__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.9rem;
  padding-bottom: 0.7rem;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.sc-card__title {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.sc-card__hint {
  font-size: 12px;
  font-weight: 600;
  color: #8b949e;
}

.sc-section-label {
  margin: 0.35rem 0 0.35rem;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #334155;
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
  margin-top: 0.35rem;
  padding: 0.75rem 0.9rem;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(15, 23, 42, 0.05);
}
.sc-location-summary {
  flex: 1;
  min-width: 200px;
}
.sc-coord-line {
  font-family: var(--okfood-font-number);
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
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 0.85rem;
  margin-bottom: 0.65rem;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(15, 23, 42, 0.05);
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
  font-family: var(--okfood-font-number);
  font-size: 13px;
}
.sc-input-el {
  width: 100%;
}
.store-config-page :deep(.el-input__wrapper),
.store-config-page :deep(.el-select__wrapper) {
  min-height: 40px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
}
.store-config-page :deep(.el-input__wrapper.is-focus),
.store-config-page :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}
.sc-input-el--mono :deep(.el-input__inner) {
  font-family: var(--okfood-font-number);
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
  width: 76px;
  height: 76px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: linear-gradient(160deg, #fff, color-mix(in srgb, var(--el-color-primary) 14%, #fff));
  box-shadow: 0 8px 18px color-mix(in srgb, var(--el-color-primary) 18%, transparent);
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
  .sc-coord-grid,
  .sc-pair {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 900px) {
  .sc-page-head {
    flex-direction: column;
    align-items: stretch;
  }

  .sc-blocks {
    grid-template-columns: 1fr;
  }
  }
</style>

<style>
/* 地图弹窗 teleport 到 body，圆角与玻璃边单独写在非 scoped 样式里 */
.sc-location-dialog.el-dialog {
  border-radius: 22px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.82);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 18px 48px rgba(25, 45, 55, 0.12);
}
.sc-location-dialog .el-dialog__header {
  margin-right: 0;
  padding: 16px 20px 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}
.sc-location-dialog .el-dialog__title {
  font-weight: 800;
  letter-spacing: -0.02em;
}
.sc-location-dialog .el-dialog__footer {
  padding: 12px 20px 16px;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}
</style>
