<script setup>
defineOptions({ name: 'TenantsView' })
import { ref, onMounted, computed } from 'vue'
import { Building2, Plug } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const loading = ref(false)
const overview = ref(null)
const tenants = ref([])
const tenantDialog = ref(false)
const tenantSaving = ref(false)
const tenantEditId = ref(null)
const tenantForm = ref({ name: '', is_active: true })

const adminsDialog = ref(false)
const adminsLoading = ref(false)
const currentTenant = ref(null)
const admins = ref([])

const adminDialog = ref(false)
const adminSaving = ref(false)
const adminEdit = ref(null)
const adminForm = ref({ username: '', password: '', role: 'full', is_active: true })

const roleLabel = (r) => {
  const x = String(r || '').toLowerCase()
  if (x === 'full') return '店主/完整'
  if (x === 'delivery') return '配送'
  if (x === 'support') return '客服'
  if (x === 'system') return '平台'
  return r || '—'
}

const storeDialog = ref(false)
const storeSaving = ref(false)
const storePatchingId = ref(null)
const storeForm = ref({
  name: '',
  leave_deadline_time: '21:00',
  is_active: true,
  sf_nightly_auto_push_enabled: false,
})

const integrationDialog = ref(false)
const integrationLoading = ref(false)
const integrationSaving = ref(false)
/** @type {import('vue').Ref<Record<string, any> | null>} */
const integrationLoaded = ref(null)
const integrationForm = ref({
  wx_mini_appid: '',
  wx_mini_secret_input: '',
  wechat_pay_mch_id: '',
  wechat_pay_api_key_input: '',
  wechat_pay_notify_url: '',
  wechat_pay_ssl_cert_path: '',
  wechat_pay_ssl_key_path: '',
  wx_subscribe_delivery_tmpl_id: '',
  wx_subscribe_renew_tmpl_id: '',
  sf_open_dev_id: null,
  sf_open_secret_input: '',
  sf_open_shop_id: '',
  sf_open_shop_type: null,
  sf_pickup_phone: '',
  sf_pickup_address: '',
  sf_city_name: '',
  extra_json: '',
})
const integrationFlags = ref({
  wx_mini_secret_set: false,
  wechat_pay_api_key_set: false,
  sf_open_secret_set: false,
  clear_wx_mini_secret: false,
  clear_wechat_pay_api_key: false,
  clear_sf_open_secret: false,
})

const storesDialog = ref(false)
const storesLoading = ref(false)
const stores = ref([])

async function loadOverview() {
  if (!adminAccessToken.value) return
  try {
    overview.value = await apiJson('/api/admin/system/overview', {}, { auth: true })
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    overview.value = null
  }
}

async function loadTenants() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    tenants.value = await apiJson('/api/admin/system/tenants', {}, { auth: true })
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

function openCreateTenant() {
  tenantEditId.value = null
  tenantForm.value = { name: '', is_active: true }
  tenantDialog.value = true
}

function openEditTenant(row) {
  tenantEditId.value = row.id
  tenantForm.value = { name: row.name || '', is_active: row.is_active !== false }
  tenantDialog.value = true
}

async function saveTenant() {
  const name = String(tenantForm.value.name || '').trim()
  if (!name) {
    showToast('请填写租户名称', 'error')
    return
  }
  tenantSaving.value = true
  try {
    if (tenantEditId.value == null) {
      await apiJson(
        '/api/admin/system/tenants',
        {
          method: 'POST',
          body: JSON.stringify({ name, is_active: tenantForm.value.is_active }),
        },
        { auth: true },
      )
      showToast('已创建', 'success')
    } else {
      await apiJson(
        `/api/admin/system/tenants/${tenantEditId.value}`,
        {
          method: 'PATCH',
          body: JSON.stringify({ name, is_active: tenantForm.value.is_active }),
        },
        { auth: true },
      )
      showToast('已保存', 'success')
    }
    tenantDialog.value = false
    await loadOverview()
    await loadTenants()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    tenantSaving.value = false
  }
}

async function deactivateTenant(row) {
  if (!row || !row.id) return
  const ok = window.confirm(`确定停用租户「${row.name}」？停用后仍可编辑恢复。`)
  if (!ok) return
  try {
    await apiJson(`/api/admin/system/tenants/${row.id}`, { method: 'DELETE' }, { auth: true })
    showToast('已停用', 'success')
    await loadOverview()
    await loadTenants()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function openAdmins(row) {
  currentTenant.value = row
  adminsDialog.value = true
  await loadAdminsForTenant(row.id)
}

async function openStores(row) {
  currentTenant.value = row
  storesDialog.value = true
  await loadStoresForTenant(row.id)
}

function resetIntegrationFormFromPayload(data) {
  integrationLoaded.value = data && typeof data === 'object' ? { ...data } : null
  integrationForm.value = {
    wx_mini_appid: data?.wx_mini_appid != null ? String(data.wx_mini_appid) : '',
    wx_mini_secret_input: '',
    wechat_pay_mch_id: data?.wechat_pay_mch_id != null ? String(data.wechat_pay_mch_id) : '',
    wechat_pay_api_key_input: '',
    wechat_pay_notify_url: data?.wechat_pay_notify_url != null ? String(data.wechat_pay_notify_url) : '',
    wechat_pay_ssl_cert_path:
      data?.wechat_pay_ssl_cert_path != null ? String(data.wechat_pay_ssl_cert_path) : '',
    wechat_pay_ssl_key_path:
      data?.wechat_pay_ssl_key_path != null ? String(data.wechat_pay_ssl_key_path) : '',
    wx_subscribe_delivery_tmpl_id:
      data?.wx_subscribe_delivery_tmpl_id != null ? String(data.wx_subscribe_delivery_tmpl_id) : '',
    wx_subscribe_renew_tmpl_id:
      data?.wx_subscribe_renew_tmpl_id != null ? String(data.wx_subscribe_renew_tmpl_id) : '',
    sf_open_dev_id: data?.sf_open_dev_id != null ? Number(data.sf_open_dev_id) : null,
    sf_open_secret_input: '',
    sf_open_shop_id: data?.sf_open_shop_id != null ? String(data.sf_open_shop_id) : '',
    sf_open_shop_type: data?.sf_open_shop_type != null ? Number(data.sf_open_shop_type) : null,
    sf_pickup_phone: data?.sf_pickup_phone != null ? String(data.sf_pickup_phone) : '',
    sf_pickup_address: data?.sf_pickup_address != null ? String(data.sf_pickup_address) : '',
    sf_city_name: data?.sf_city_name != null ? String(data.sf_city_name) : '',
    extra_json: data?.extra_json != null ? String(data.extra_json) : '',
  }
  integrationFlags.value = {
    wx_mini_secret_set: Boolean(data?.wx_mini_secret_set),
    wechat_pay_api_key_set: Boolean(data?.wechat_pay_api_key_set),
    sf_open_secret_set: Boolean(data?.sf_open_secret_set),
    clear_wx_mini_secret: false,
    clear_wechat_pay_api_key: false,
    clear_sf_open_secret: false,
  }
}

async function openIntegration(row) {
  currentTenant.value = row
  integrationDialog.value = true
  const tid = row && row.id
  if (tid == null) return
  integrationLoading.value = true
  try {
    const data = await apiJson(`/api/admin/system/tenants/${tid}/integration-settings`, {}, { auth: true })
    resetIntegrationFormFromPayload(data)
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载对接配置失败', 'error')
    resetIntegrationFormFromPayload(null)
  } finally {
    integrationLoading.value = false
  }
}

async function saveIntegration() {
  const tid = currentTenant.value && currentTenant.value.id
  if (tid == null) return

  const extra = String(integrationForm.value.extra_json || '').trim()
  if (extra) {
    try {
      JSON.parse(extra)
    } catch {
      showToast('扩展 JSON 格式不合法', 'error')
      return
    }
  }

  const body = {}
  const t = (v) => String(v ?? '').trim()

  body.wx_mini_appid = t(integrationForm.value.wx_mini_appid) || null
  body.wechat_pay_mch_id = t(integrationForm.value.wechat_pay_mch_id) || null
  body.wechat_pay_notify_url = t(integrationForm.value.wechat_pay_notify_url) || null
  body.wechat_pay_ssl_cert_path = t(integrationForm.value.wechat_pay_ssl_cert_path) || null
  body.wechat_pay_ssl_key_path = t(integrationForm.value.wechat_pay_ssl_key_path) || null
  body.wx_subscribe_delivery_tmpl_id = t(integrationForm.value.wx_subscribe_delivery_tmpl_id) || null
  body.wx_subscribe_renew_tmpl_id = t(integrationForm.value.wx_subscribe_renew_tmpl_id) || null
  body.sf_open_shop_id = t(integrationForm.value.sf_open_shop_id) || null
  body.sf_pickup_phone = t(integrationForm.value.sf_pickup_phone) || null
  body.sf_pickup_address = t(integrationForm.value.sf_pickup_address) || null
  body.sf_city_name = t(integrationForm.value.sf_city_name) || null
  body.extra_json = extra ? extra : null

  const devId = integrationForm.value.sf_open_dev_id
  body.sf_open_dev_id = devId === null || devId === '' || Number.isNaN(Number(devId)) ? null : Number(devId)
  const st = integrationForm.value.sf_open_shop_type
  body.sf_open_shop_type = st === null || st === '' || Number.isNaN(Number(st)) ? null : Number(st)

  if (integrationFlags.value.clear_wx_mini_secret) body.wx_mini_secret = ''
  else {
    const s = t(integrationForm.value.wx_mini_secret_input)
    if (s) body.wx_mini_secret = s
  }
  if (integrationFlags.value.clear_wechat_pay_api_key) body.wechat_pay_api_key = ''
  else {
    const s = t(integrationForm.value.wechat_pay_api_key_input)
    if (s) body.wechat_pay_api_key = s
  }
  if (integrationFlags.value.clear_sf_open_secret) body.sf_open_secret = ''
  else {
    const s = t(integrationForm.value.sf_open_secret_input)
    if (s) body.sf_open_secret = s
  }

  integrationSaving.value = true
  try {
    const data = await apiJson(
      `/api/admin/system/tenants/${tid}/integration-settings`,
      { method: 'PATCH', body: JSON.stringify(body) },
      { auth: true },
    )
    resetIntegrationFormFromPayload(data)
    showToast('对接配置已保存（密钥不回显）', 'success')
    await loadTenants()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    integrationSaving.value = false
  }
}

async function loadStoresForTenant(tenantId) {
  if (tenantId == null) return
  storesLoading.value = true
  try {
    stores.value = await apiJson(`/api/admin/system/tenants/${tenantId}/stores`, {}, { auth: true })
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载门店失败', 'error')
    stores.value = []
  } finally {
    storesLoading.value = false
  }
}

function openCreateStore() {
  storeForm.value = {
    name: '',
    leave_deadline_time: '21:00',
    is_active: true,
    sf_nightly_auto_push_enabled: false,
  }
  storeDialog.value = true
}

async function saveStore() {
  const tid = currentTenant.value && currentTenant.value.id
  if (tid == null) return
  const name = String(storeForm.value.name || '').trim()
  if (!name) {
    showToast('请填写门店名称', 'error')
    return
  }
  storeSaving.value = true
  try {
    const data = await apiJson(
      `/api/admin/system/tenants/${tid}/stores`,
      {
        method: 'POST',
        body: JSON.stringify({
          name,
          leave_deadline_time: String(storeForm.value.leave_deadline_time || '21:00').trim(),
          is_active: storeForm.value.is_active !== false,
          sf_nightly_auto_push_enabled: storeForm.value.sf_nightly_auto_push_enabled === true,
        }),
      },
      { auth: true },
    )
    storeDialog.value = false
    const sid = data && data.id != null ? data.id : '—'
    showToast(`门店已创建，门店 ID=${sid}；管理端 API 需带 store_id=${sid}`, 'success')
    await loadStoresForTenant(tid)
    await loadOverview()
    await loadTenants()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '创建失败', 'error')
  } finally {
    storeSaving.value = false
  }
}

async function patchStoreNightly(row, enabled) {
  const tid = currentTenant.value && currentTenant.value.id
  if (tid == null || !row) return
  storePatchingId.value = row.id
  try {
    await apiJson(
      `/api/admin/system/tenants/${tid}/stores/${row.id}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ sf_nightly_auto_push_enabled: enabled }),
      },
      { auth: true },
    )
    row.sf_nightly_auto_push_enabled = enabled
    showToast('已保存自动推单设置', 'success')
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
    void loadStoresForTenant(tid)
  } finally {
    storePatchingId.value = null
  }
}

async function loadAdminsForTenant(tenantId) {
  if (tenantId == null) return
  adminsLoading.value = true
  try {
    admins.value = await apiJson(`/api/admin/system/tenants/${tenantId}/admins`, {}, { auth: true })
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载管理员失败', 'error')
    admins.value = []
  } finally {
    adminsLoading.value = false
  }
}

function openCreateAdmin() {
  adminEdit.value = null
  adminForm.value = { username: '', password: '', role: 'full', is_active: true }
  adminDialog.value = true
}

function openEditAdmin(row) {
  if (String(row.role || '').toLowerCase() === 'system') {
    showToast('平台管理员请在数据库中维护', 'error')
    return
  }
  adminEdit.value = row
  adminForm.value = {
    username: row.username || '',
    password: '',
    role: String(row.role || 'full').toLowerCase(),
    is_active: row.is_active !== false,
  }
  adminDialog.value = true
}

const adminDialogTitle = computed(() => (adminEdit.value ? '编辑管理员' : '新增管理员'))

async function saveAdmin() {
  const tid = currentTenant.value && currentTenant.value.id
  if (tid == null) return
  if (!adminEdit.value) {
    const uname = String(adminForm.value.username || '').trim()
    const pwd = String(adminForm.value.password || '')
    if (!uname) {
      showToast('请填写用户名', 'error')
      return
    }
    if (pwd.length < 6) {
      showToast('密码至少 6 位', 'error')
      return
    }
  }
  adminSaving.value = true
  try {
    if (!adminEdit.value) {
      const uname = String(adminForm.value.username || '').trim()
      const pwd = String(adminForm.value.password || '')
      await apiJson(
        `/api/admin/system/tenants/${tid}/admins`,
        {
          method: 'POST',
          body: JSON.stringify({
            username: uname,
            password: pwd,
            role: adminForm.value.role,
          }),
        },
        { auth: true },
      )
      showToast('已创建', 'success')
    } else {
      const body = {}
      const pwd = String(adminForm.value.password || '').trim()
      if (pwd) body.password = pwd
      if (adminForm.value.role) body.role = adminForm.value.role
      body.is_active = adminForm.value.is_active
      await apiJson(
        `/api/admin/system/tenants/${tid}/admins/${adminEdit.value.id}`,
        {
          method: 'PATCH',
          body: JSON.stringify(body),
        },
        { auth: true },
      )
      showToast('已保存', 'success')
    }
    adminDialog.value = false
    await loadAdminsForTenant(tid)
    await loadOverview()
    await loadTenants()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    adminSaving.value = false
  }
}

async function deactivateAdmin(row) {
  const tid = currentTenant.value && currentTenant.value.id
  if (tid == null || !row) return
  if (String(row.role || '').toLowerCase() === 'system') {
    showToast('不能在此处停用平台管理员', 'error')
    return
  }
  const ok = window.confirm(`确定停用管理员「${row.username}」？`)
  if (!ok) return
  try {
    await apiJson(
      `/api/admin/system/tenants/${tid}/admins/${row.id}`,
      { method: 'DELETE' },
      { auth: true },
    )
    showToast('已停用', 'success')
    await loadAdminsForTenant(tid)
    await loadOverview()
    await loadTenants()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

onMounted(async () => {
  await loadOverview()
  await loadTenants()
})
</script>

<template>
  <div class="tenants-page">
    <div class="page-head">
      <div class="page-head-title">
        <Building2 :size="22" stroke-width="2" class="page-head-icon" />
        <div>
          <h2>租户管理</h2>
          <p class="page-head-sub">全库规模一览；维护租户、对接配置、门店与店主后台账号</p>
        </div>
      </div>
      <el-button type="primary" @click="openCreateTenant">新建租户</el-button>
    </div>

    <div v-if="overview" class="overview-stats">
      <div class="stat-card">
        <span class="stat-label">租户总数</span>
        <strong class="stat-value">{{ overview.tenants_total }}</strong>
        <span class="stat-sub">启用 {{ overview.tenants_active }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">门店总数</span>
        <strong class="stat-value">{{ overview.stores_total }}</strong>
        <span class="stat-sub">启用 {{ overview.stores_active }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">活跃管理员</span>
        <strong class="stat-value">{{ overview.admin_users_active }}</strong>
        <span class="stat-sub">含各租户与平台账号</span>
      </div>
    </div>

    <div class="onboarding-tip">
      <strong>给新门店开账号：</strong>
      ① 新建或选中租户 → 点<strong>门店</strong>新增门店，记下列表里的<strong>门店 ID</strong>。② 同一租户下点<strong>管理员</strong>新增店主账号（role=full）。
      ③ 店主登录后，若该租户下只有一家店且 ID 为 1，管理后台默认可用；若为多门店或非 1，请求管理 API 时需带查询参数
      <code class="tip-code">store_id=&lt;门店ID&gt;</code>（当前 Vue 管理端多数仍默认 1，需扩展时可再统一加门店切换）。
    </div>

    <el-card shadow="never" class="table-card" v-loading="loading">
      <el-table :data="tenants" style="width: 100%" table-layout="auto" empty-text="暂无租户">
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="store_count" label="门店数" width="90" />
        <el-table-column prop="admin_count" label="管理员(活跃)" width="120" />
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openStores(row)">门店</el-button>
            <el-button link type="primary" @click="openAdmins(row)">管理员</el-button>
            <el-button link type="primary" @click="openIntegration(row)">
              <Plug :size="14" stroke-width="2" class="btn-inline-icon" />
              对接
            </el-button>
            <el-button link type="primary" @click="openEditTenant(row)">编辑</el-button>
            <el-button link type="danger" @click="deactivateTenant(row)">停用</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="tenantDialog" :title="tenantEditId == null ? '新建租户' : '编辑租户'" width="420px">
      <el-form label-position="top">
        <el-form-item label="租户名称">
          <el-input v-model="tenantForm.name" maxlength="128" show-word-limit placeholder="例如：某某餐饮" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="tenantForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tenantDialog = false">取消</el-button>
        <el-button type="primary" :loading="tenantSaving" @click="saveTenant">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="storesDialog" :title="currentTenant ? `门店：${currentTenant.name}` : '门店'" size="560px">
      <div class="drawer-toolbar">
        <el-button type="primary" size="small" @click="openCreateStore">新建门店</el-button>
      </div>
      <el-table v-loading="storesLoading" :data="stores" size="small" empty-text="暂无门店">
        <el-table-column prop="id" label="门店ID" width="88" />
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="leave_deadline_time" label="请假截止" width="100" />
        <el-table-column label="顺丰自动推单" min-width="120">
          <template #default="{ row }">
            <el-switch
              :model-value="row.sf_nightly_auto_push_enabled === true"
              :disabled="storesLoading || storePatchingId === row.id"
              inline-prompt
              active-text="开"
              inactive-text="关"
              @change="(v) => patchStoreNightly(row, v)"
            />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="84">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-dialog v-model="storeDialog" title="新建门店" width="440px">
      <el-form label-position="top">
        <el-form-item label="门店名称">
          <el-input v-model="storeForm.name" maxlength="128" placeholder="例如：浦东店" />
        </el-form-item>
        <el-form-item label="当日请假截止时间">
          <el-input v-model="storeForm.leave_deadline_time" placeholder="21:00 或 21:00:00" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="storeForm.is_active" />
        </el-form-item>
        <el-form-item label="顺丰自动推单">
          <div class="store-nightly-wrap">
            <el-switch v-model="storeForm.sf_nightly_auto_push_enabled" />
            <span class="store-nightly-hint">每日 07:00（上海）自动推送<strong>当日</strong>待配送订单；关闭后仅能在配送大表手动推单</span>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="storeDialog = false">取消</el-button>
        <el-button type="primary" :loading="storeSaving" @click="saveStore">创建</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="integrationDialog"
      :title="currentTenant ? `对接配置：${currentTenant.name}` : '对接配置'"
      size="640px"
      class="integration-drawer"
    >
      <div v-loading="integrationLoading" class="integration-drawer-body">
        <p class="integration-drawer-tip">
          此处为<strong>租户级覆盖</strong>：未填写或已勾除的字段，运行时将与支付/物流回调等逻辑一并<strong>回退到服务器全局 .env</strong>。密钥仅支持设置或清除，保存后不回显明文。
        </p>
        <p v-if="integrationLoaded && integrationLoaded.updated_at" class="integration-meta">
          最近保存：{{ integrationLoaded.updated_at || '—' }}
        </p>

        <el-form label-position="top" class="integration-form">
          <el-divider content-position="left">微信小程序</el-divider>
          <el-form-item label="AppId">
            <el-input v-model="integrationForm.wx_mini_appid" maxlength="64" placeholder="留空则用全局 WX_MINI_APPID" />
          </el-form-item>
          <el-form-item label="AppSecret">
            <div class="secret-row">
              <el-input
                v-model="integrationForm.wx_mini_secret_input"
                type="password"
                show-password
                maxlength="128"
                :disabled="integrationFlags.clear_wx_mini_secret"
                placeholder="留空不改；填写则更新为新密钥"
              />
              <el-tag v-if="integrationFlags.wx_mini_secret_set" type="info" size="small">已配置密钥</el-tag>
            </div>
            <el-checkbox v-model="integrationFlags.clear_wx_mini_secret" size="small">清除租户 Secret（回退全局）</el-checkbox>
          </el-form-item>

          <el-divider content-position="left">微信支付（APIv2）</el-divider>
          <el-form-item label="商户号 mch_id">
            <el-input v-model="integrationForm.wechat_pay_mch_id" maxlength="32" placeholder="留空则用全局 WECHAT_PAY_MCH_ID" />
          </el-form-item>
          <el-form-item label="API 密钥">
            <div class="secret-row">
              <el-input
                v-model="integrationForm.wechat_pay_api_key_input"
                type="password"
                show-password
                maxlength="128"
                :disabled="integrationFlags.clear_wechat_pay_api_key"
                placeholder="32 位移；留空不改"
              />
              <el-tag v-if="integrationFlags.wechat_pay_api_key_set" type="info" size="small">已配置</el-tag>
            </div>
            <el-checkbox v-model="integrationFlags.clear_wechat_pay_api_key" size="small">清除密钥（回退全局）</el-checkbox>
          </el-form-item>
          <el-form-item label="支付 notify_url">
            <el-input
              v-model="integrationForm.wechat_pay_notify_url"
              maxlength="512"
              placeholder="留空则用全局 WECHAT_PAY_NOTIFY_URL"
            />
          </el-form-item>
          <el-form-item
            label="退款 API 证书 cert 路径（apiclient_cert.pem）"
            :title="'租户内各门店未单独配置时的默认路径；门店可在「门店配置」覆盖'"
          >
            <el-input
              v-model="integrationForm.wechat_pay_ssl_cert_path"
              maxlength="512"
              placeholder="例：E:/certs/apiclient_cert.pem；留空则仅用门店或全局 .env"
              class="mono-input"
            />
          </el-form-item>
          <el-form-item
            label="退款 API 证书 key 路径（apiclient_key.pem）"
            :title="'租户默认 key 路径；优先级：门店 > 租户 > WECHAT_PAY_SSL_KEY_PATH'"
          >
            <el-input
              v-model="integrationForm.wechat_pay_ssl_key_path"
              maxlength="512"
              placeholder="例：E:/certs/apiclient_key.pem"
              class="mono-input"
            />
          </el-form-item>

          <el-divider content-position="left">订阅消息</el-divider>
          <el-form-item label="配送类模板 ID">
            <el-input
              v-model="integrationForm.wx_subscribe_delivery_tmpl_id"
              maxlength="128"
              placeholder="可选；留空则用全局或代码默认"
            />
          </el-form-item>
          <el-form-item label="续费提醒模板 ID">
            <el-input
              v-model="integrationForm.wx_subscribe_renew_tmpl_id"
              maxlength="128"
              placeholder="完善资料页授权后低余额触达；留空则用全局 .env"
            />
          </el-form-item>

          <el-divider content-position="left">顺丰开放平台（同城等）</el-divider>
          <el-form-item label="dev_id">
            <el-input-number
              v-model="integrationForm.sf_open_dev_id"
              :min="0"
              :controls="true"
              placeholder="留空则用全局"
              class="w-num"
            />
          </el-form-item>
          <el-form-item label="secret">
            <div class="secret-row">
              <el-input
                v-model="integrationForm.sf_open_secret_input"
                type="password"
                show-password
                maxlength="255"
                :disabled="integrationFlags.clear_sf_open_secret"
                placeholder="留空不改"
              />
              <el-tag v-if="integrationFlags.sf_open_secret_set" type="info" size="small">已填</el-tag>
            </div>
            <el-checkbox v-model="integrationFlags.clear_sf_open_secret" size="small">清除 secret（回退全局）</el-checkbox>
          </el-form-item>
          <el-form-item label="shop_id（门店）">
            <el-input v-model="integrationForm.sf_open_shop_id" maxlength="64" placeholder="留空则用全局 SF_OPEN_SHOP_ID" />
          </el-form-item>
          <el-form-item label="shop_type">
            <el-select v-model="integrationForm.sf_open_shop_type" clearable placeholder="留空则用全局" style="width: 100%">
              <el-option label="1" :value="1" />
              <el-option label="2" :value="2" />
            </el-select>
          </el-form-item>
          <el-form-item label="取件电话">
            <el-input v-model="integrationForm.sf_pickup_phone" maxlength="32" placeholder="留空则用全局" />
          </el-form-item>
          <el-form-item label="取件地址">
            <el-input v-model="integrationForm.sf_pickup_address" maxlength="512" type="textarea" :rows="2" placeholder="留空则用全局" />
          </el-form-item>
          <el-form-item label="城市名（如开单城市）">
            <el-input v-model="integrationForm.sf_city_name" maxlength="64" placeholder="留空则用全局 SF_CITY_NAME" />
          </el-form-item>

          <el-divider content-position="left">扩展</el-divider>
          <el-form-item label="extra_json">
            <el-input v-model="integrationForm.extra_json" type="textarea" :rows="4" placeholder='合法 JSON 字符串；留空可清除扩展字段' />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <div class="integration-drawer-footer">
          <el-button @click="integrationDialog = false">关闭</el-button>
          <el-button type="primary" :loading="integrationSaving" :disabled="integrationLoading" @click="saveIntegration">
            保存
          </el-button>
        </div>
      </template>
    </el-drawer>

    <el-drawer v-model="adminsDialog" :title="currentTenant ? `管理员：${currentTenant.name}` : '管理员'" size="520px">
      <div class="drawer-toolbar">
        <el-button type="primary" size="small" @click="openCreateAdmin">新增管理员</el-button>
      </div>
      <el-table v-loading="adminsLoading" :data="admins" size="small" empty-text="暂无管理员">
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column label="角色" width="110">
          <template #default="{ row }">{{ roleLabel(row.role) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="84">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEditAdmin(row)">编辑</el-button>
            <el-button link type="danger" @click="deactivateAdmin(row)">停用</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-dialog v-model="adminDialog" :title="adminDialogTitle" width="440px">
      <el-form label-position="top">
        <el-form-item v-if="!adminEdit" label="用户名">
          <el-input v-model="adminForm.username" maxlength="64" autocomplete="off" />
        </el-form-item>
        <el-form-item v-else label="用户名">
          <el-input v-model="adminForm.username" disabled />
        </el-form-item>
        <el-form-item :label="adminEdit ? '新密码（留空不改）' : '密码'">
          <el-input v-model="adminForm.password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="adminForm.role" style="width: 100%">
            <el-option label="店主/完整 (full)" value="full" />
            <el-option label="仅配送 (delivery)" value="delivery" />
            <el-option label="客服 (support)" value="support" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="adminEdit" label="启用">
          <el-switch v-model="adminForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adminDialog = false">取消</el-button>
        <el-button type="primary" :loading="adminSaving" @click="saveAdmin">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tenants-page {
  max-width: 1200px;
  margin: 0 auto;
}
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.page-head-title {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.page-head-title h2 {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 600;
}
.page-head-sub {
  margin: 6px 0 0;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.55);
}
.page-head-icon {
  margin-top: 4px;
  color: #facc15;
  flex-shrink: 0;
}
.table-card {
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.15);
}
.drawer-toolbar {
  margin-bottom: 12px;
}
.overview-stats {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-label {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.55);
}
.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #f8fafc;
}
.stat-sub {
  font-size: 0.75rem;
  color: rgba(148, 163, 184, 0.9);
}
.onboarding-tip {
  font-size: 0.85rem;
  line-height: 1.55;
  color: rgba(226, 232, 240, 0.88);
  background: rgba(30, 58, 138, 0.25);
  border: 1px solid rgba(96, 165, 250, 0.25);
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 16px;
}
.tip-code {
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  color: #fde047;
}
.btn-inline-icon {
  display: inline-block;
  vertical-align: -0.2em;
  margin-right: 4px;
}
.integration-drawer-tip {
  margin: 0 0 12px;
  font-size: 0.85rem;
  line-height: 1.55;
  color: rgba(226, 232, 240, 0.88);
}
.integration-meta {
  margin: 0 0 16px;
  font-size: 0.8rem;
  color: rgba(148, 163, 184, 0.95);
}
.integration-drawer-body {
  min-height: 200px;
}
.integration-form :deep(.el-divider__text) {
  font-weight: 600;
  color: #e2e8f0;
}
.secret-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.secret-row .el-input {
  flex: 1;
}
.w-num {
  width: 100%;
}
.w-num :deep(.el-input__wrapper) {
  width: 100%;
}
.integration-drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.store-nightly-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.store-nightly-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
  line-height: 1.45;
}
</style>
