<script setup>
defineOptions({ name: 'PrinterManageView' })
import { ref, computed, watch, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import { apiJson, adminAccessToken, adminStoreId, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import { useStorePrint } from '../../composables/useStorePrint.js'
import { PRINT_BRANDS, brandMeta } from '../../constants/printBrands.js'
import { PAPER_PRESETS, presetSize } from '../../constants/printPaperPresets.js'
import { listLocalPrinters } from '../../utils/print/lodopLoader.js'

const { testProfile, storeQuery } = useStorePrint()

const loading = ref(false)
const savingCreds = ref(false)
const dialogOpen = ref(false)
const editId = ref(null)
const profiles = ref([])
const localPrinters = ref([])
const loadingPrinters = ref(false)
const creds = ref({
  feie_user: '',
  feie_ukey: '',
  xprinter_user: '',
  xprinter_user_key: '',
  yilian_partner: '',
  yilian_apikey: '',
})

const form = ref({
  name: '',
  brand: 'local_label',
  cloud_sn: '',
  cloud_device_key: '',
  paper_preset: '80x60',
  paper_width_mm: 80,
  paper_height_mm: 60,
  local_printer_name_hint: '',
  margin_top_mm: 2,
  margin_left_mm: 2,
  is_default: false,
})

const brandInfo = computed(() => brandMeta(form.value.brand))

async function refreshLocalPrinters() {
  loadingPrinters.value = true
  try {
    localPrinters.value = await listLocalPrinters()
    if (!localPrinters.value.length) {
      showToast('未检测到本机打印机，请确认驱动已安装', 'error')
    }
  } catch (e) {
    showToast(e?.message || '无法读取本机打印机，请确认 C-Lodop 已启动', 'error')
    localPrinters.value = []
  } finally {
    loadingPrinters.value = false
  }
}

watch(dialogOpen, (open) => {
  if (open && !brandMeta(form.value.brand).cloud) {
    void refreshLocalPrinters()
  }
})

watch(
  () => form.value.brand,
  (brand) => {
    if (dialogOpen.value && !brandMeta(brand).cloud) {
      void refreshLocalPrinters()
    }
  },
)

async function loadAll() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const [list, c] = await Promise.all([
      apiJson(`/api/admin/store-print/profiles?${storeQuery()}`, {}, { auth: true }),
      apiJson(`/api/admin/store-print/cloud-credentials?${storeQuery()}`, {}, { auth: true }),
    ])
    profiles.value = Array.isArray(list) ? list : []
    creds.value = {
      feie_user: c?.feie_user || '',
      feie_ukey: '',
      xprinter_user: c?.xprinter_user || '',
      xprinter_user_key: '',
      yilian_partner: c?.yilian_partner || '',
      yilian_apikey: '',
    }
  } catch (e) {
    handleAdminLogout(e)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editId.value = null
  form.value = {
    name: '',
    brand: 'local_label',
    cloud_sn: '',
    cloud_device_key: '',
    paper_preset: '100x150',
    paper_width_mm: 100,
    paper_height_mm: 150,
    local_printer_name_hint: '',
    margin_top_mm: 2,
    margin_left_mm: 2,
    is_default: profiles.value.length === 0,
  }
  dialogOpen.value = true
}

function openEdit(row) {
  editId.value = row.id
  form.value = {
    name: row.name,
    brand: row.brand,
    cloud_sn: row.cloud_sn || '',
    cloud_device_key: '',
    paper_preset: row.paper_preset,
    paper_width_mm: row.paper_width_mm,
    paper_height_mm: row.paper_height_mm,
    local_printer_name_hint: row.local_printer_name_hint || '',
    margin_top_mm: row.margin_top_mm,
    margin_left_mm: row.margin_left_mm,
    is_default: row.is_default,
  }
  dialogOpen.value = true
}

function onPresetChange(val) {
  const p = presetSize(val)
  if (p?.width) {
    form.value.paper_width_mm = p.width
    form.value.paper_height_mm = p.height
  }
}

async function saveCreds() {
  savingCreds.value = true
  try {
    const body = {}
    for (const [k, v] of Object.entries(creds.value)) {
      if (v != null && String(v).trim()) body[k] = String(v).trim()
    }
    await apiJson(`/api/admin/store-print/cloud-credentials?${storeQuery()}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }, { auth: true })
    showToast('云打印凭证已保存', 'success')
    await loadAll()
  } catch (e) {
    showToast(e?.message || '保存失败', 'error')
    handleAdminLogout(e)
  } finally {
    savingCreds.value = false
  }
}

async function saveProfile() {
  if (!brandMeta(form.value.brand).cloud && !String(form.value.local_printer_name_hint || '').trim()) {
    showToast('请选择或填写本机 Windows 打印机名称', 'error')
    return
  }
  try {
    const payload = { ...form.value }
    if (editId.value) {
      await apiJson(
        `/api/admin/store-print/profiles/${editId.value}?${storeQuery()}`,
        { method: 'PATCH', body: JSON.stringify(payload) },
        { auth: true },
      )
      showToast('已更新', 'success')
    } else {
      await apiJson(
        `/api/admin/store-print/profiles?${storeQuery()}`,
        { method: 'POST', body: JSON.stringify(payload) },
        { auth: true },
      )
      showToast('已添加', 'success')
    }
    dialogOpen.value = false
    await loadAll()
  } catch (e) {
    showToast(e?.message || '保存失败', 'error')
    handleAdminLogout(e)
  }
}

async function onTest(row) {
  await testProfile(row.id)
}

async function onDelete(row) {
  if (!window.confirm(`停用打印机「${row.name}」？`)) return
  try {
    await apiJson(
      `/api/admin/store-print/profiles/${row.id}?${storeQuery()}`,
      { method: 'DELETE' },
      { auth: true },
    )
    showToast('已停用', 'success')
    await loadAll()
  } catch (e) {
    showToast(e?.message || '操作失败', 'error')
  }
}

onMounted(() => {
  void loadAll()
})
</script>

<template>
  <section class="printer-manage animate-up">
    <div class="pm-card pm-card--tip">
      <p class="pm-tip">
        本地标签机需安装
        <a href="http://www.lodop.net" target="_blank" rel="noopener">C-Lodop</a>
        与打印机驱动；云打印机须先配置下方开发者凭证，再添加 SN。
      </p>
    </div>

    <div class="pm-card">
      <h3 class="pm-card__title">云打印开发者凭证（本租户）</h3>
      <el-form label-position="top" class="pm-creds-form">
        <div class="pm-creds-grid">
          <el-form-item label="飞鹅 USER">
            <el-input v-model="creds.feie_user" placeholder="飞鹅开放平台账号" />
          </el-form-item>
          <el-form-item label="飞鹅 UKEY">
            <el-input v-model="creds.feie_ukey" type="password" show-password placeholder="留空则不修改" />
          </el-form-item>
          <el-form-item label="芯烨开发者账号">
            <el-input v-model="creds.xprinter_user" />
          </el-form-item>
          <el-form-item label="芯烨 UserKEY">
            <el-input v-model="creds.xprinter_user_key" type="password" show-password placeholder="留空则不修改" />
          </el-form-item>
          <el-form-item label="易联云 partner">
            <el-input v-model="creds.yilian_partner" />
          </el-form-item>
          <el-form-item label="易联云 apikey">
            <el-input v-model="creds.yilian_apikey" type="password" show-password placeholder="留空则不修改" />
          </el-form-item>
        </div>
        <el-button type="primary" :loading="savingCreds" @click="saveCreds">保存凭证</el-button>
      </el-form>
    </div>

    <div class="pm-card">
      <div class="pm-toolbar">
        <h3 class="pm-card__title">打印机列表</h3>
        <el-button type="primary" @click="openCreate">
          <Plus :size="16" class="pm-btn-icon" />
          添加打印机
        </el-button>
      </div>
      <el-table v-loading="loading" :data="profiles" stripe>
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="brand_label" label="品牌" min-width="120" />
        <el-table-column label="纸张" width="100">
          <template #default="{ row }">{{ row.paper_width_mm }}×{{ row.paper_height_mm }}mm</template>
        </el-table-column>
        <el-table-column prop="cloud_sn" label="SN/本机名" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.cloud_sn || row.local_printer_name_hint || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="默认" width="72">
          <template #default="{ row }">{{ row.is_default ? '是' : '' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="onTest(row)">测试</el-button>
            <el-button link type="danger" @click="onDelete(row)">停用</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogOpen" :title="editId ? '编辑打印机' : '添加打印机'" width="520px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="打印机名称" required>
          <el-input v-model="form.name" maxlength="64" />
        </el-form-item>
        <el-form-item label="打印机型号">
          <el-radio-group v-model="form.brand">
            <el-radio v-for="b in PRINT_BRANDS" :key="b.value" :value="b.value">{{ b.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="brandInfo.cloud">
          <el-form-item label="打印机 SN / 终端号" required>
            <el-input v-model="form.cloud_sn" placeholder="机身底部标签" />
          </el-form-item>
          <el-form-item v-if="brandInfo.needsKey" label="KEY / msign" required>
            <el-input v-model="form.cloud_device_key" type="password" show-password />
          </el-form-item>
        </template>
        <el-form-item v-else label="本机 Windows 打印机名称" required>
          <div class="pm-printer-pick">
            <el-select
              v-model="form.local_printer_name_hint"
              filterable
              allow-create
              default-first-option
              placeholder="从列表选择（须与「设备和打印机」中名称一致）"
              class="pm-printer-pick__select"
            >
              <el-option v-for="p in localPrinters" :key="p" :label="p" :value="p" />
            </el-select>
            <el-button :loading="loadingPrinters" @click="refreshLocalPrinters">刷新</el-button>
          </div>
          <p class="pm-paper-tip">
            「打印机名称」仅为后台备注；此处必须与 Windows 中显示的驱动名称完全一致，不能填型号简称（如 QR-488）。
          </p>
        </el-form-item>
        <el-form-item label="纸张规格">
          <el-select v-model="form.paper_preset" @change="onPresetChange">
            <el-option v-for="p in PAPER_PRESETS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
          <p v-if="form.brand === 'local_label'" class="pm-paper-tip">
            备餐面单推荐 100×150mm，与顺丰面单尺寸接近。
          </p>
        </el-form-item>
        <div v-if="form.paper_preset === 'custom'" class="pm-size-row">
          <el-form-item label="宽 mm">
            <el-input-number v-model="form.paper_width_mm" :min="20" :max="200" />
          </el-form-item>
          <el-form-item label="高 mm">
            <el-input-number v-model="form.paper_height_mm" :min="15" :max="300" />
          </el-form-item>
        </div>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" @click="saveProfile">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.printer-manage {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.pm-card {
  background: #fff;
  border-radius: 12px;
  padding: 1rem 1.25rem;
  border: 1px solid #e5e7eb;
}
.pm-card--tip {
  background: #f0fdf4;
  border-color: #bbf7d0;
}
.pm-tip {
  margin: 0;
  font-size: 0.875rem;
  color: #166534;
}
.pm-card__title {
  margin: 0 0 0.75rem;
  font-size: 1rem;
  font-weight: 700;
}
.pm-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}
.pm-toolbar .pm-card__title {
  margin: 0;
}
.pm-btn-icon {
  margin-right: 4px;
  vertical-align: middle;
}
.pm-creds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0 1rem;
}
.pm-size-row {
  display: flex;
  gap: 1rem;
}
.pm-paper-tip {
  margin: 0.35rem 0 0;
  font-size: 0.75rem;
  color: #6b7280;
}
.pm-printer-pick {
  display: flex;
  gap: 0.5rem;
  width: 100%;
}
.pm-printer-pick__select {
  flex: 1;
}
</style>
