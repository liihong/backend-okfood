<script setup>
defineOptions({ name: 'GiftCouponsView' })
import { ref, onMounted, computed } from 'vue'
import { Plus } from 'lucide-vue-next'
import { ElMessageBox } from 'element-plus'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import GiftCouponCampaignFormModal from './components/GiftCouponCampaignFormModal.vue'

const storeId = ref(1)
const campaigns = ref([])
const loading = ref(false)
const formVisible = ref(false)
const editing = ref(null)
const selectedId = ref(null)

const entitlements = ref([])
const entLoading = ref(false)
const entStatus = ref('granted')
const entPhone = ref('')
const entPage = ref(1)
const entPageSize = ref(20)
const entTotal = ref(0)
const manualPhones = ref('')
const manualGranting = ref(false)

const STATUS_CAMP = {
  draft: '草稿',
  active: '进行中',
  closed: '已结束',
}
const STATUS_ENT = {
  granted: '未核销',
  redeemed: '已核销',
  revoked: '已作废',
}

const selectedCampaign = computed(() =>
  campaigns.value.find((c) => Number(c.id) === Number(selectedId.value)) || null,
)

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewGranting = ref(false)
const previewCampaign = ref(null)
const previewItems = ref([])
const previewTotal = ref(0)

function planKindsText(kinds) {
  const map = { month: '月卡', quarter: '季卡' }
  return (Array.isArray(kinds) ? kinds : []).map((k) => map[k] || k).join('、') || '—'
}

async function loadCampaigns() {
  loading.value = true
  try {
    const data = await apiJson(
      `/api/admin/gift-coupons/campaigns?store_id=${storeId.value}`,
      {},
      { auth: true },
    )
    campaigns.value = Array.isArray(data) ? data : []
    if (selectedId.value && !campaigns.value.some((c) => Number(c.id) === Number(selectedId.value))) {
      selectedId.value = null
    }
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

async function loadEntitlements() {
  if (!selectedId.value) {
    entitlements.value = []
    entTotal.value = 0
    return
  }
  entLoading.value = true
  try {
    const q = new URLSearchParams()
    q.set('store_id', String(storeId.value))
    q.set('campaign_id', String(selectedId.value))
    q.set('page', String(entPage.value))
    q.set('page_size', String(entPageSize.value))
    if (entStatus.value) q.set('status', entStatus.value)
    const ph = String(entPhone.value || '').trim()
    if (ph) q.set('member_phone', ph)
    const data = await apiJson(`/api/admin/gift-coupons/entitlements?${q.toString()}`, {}, { auth: true })
    entitlements.value = Array.isArray(data?.items) ? data.items : []
    entTotal.value = Number(data?.total) || 0
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '加载资格失败', 'error')
  } finally {
    entLoading.value = false
  }
}

function openCreate() {
  editing.value = null
  formVisible.value = true
}

function openEdit(row) {
  if (row.status !== 'draft') {
    showToast('仅草稿可改规则', 'error')
    return
  }
  editing.value = row
  formVisible.value = true
}

async function onFormSaved() {
  formVisible.value = false
  await loadCampaigns()
}

function selectCampaign(row) {
  selectedId.value = row.id
  entPage.value = 1
  void loadEntitlements()
}

async function openPreview(row) {
  previewCampaign.value = row
    previewItems.value = []
    previewTotal.value = 0
    previewVisible.value = true
    previewLoading.value = true
    try {
      const data = await apiJson(
        `/api/admin/gift-coupons/campaigns/${row.id}/preview?store_id=${storeId.value}`,
        { method: 'POST' },
        { auth: true },
      )
      const items = Array.isArray(data?.items) ? data.items : []
      previewItems.value = items
      previewTotal.value = Number(data?.total) || items.length
    } catch (e) {
      if (handleAdminLogout(e)) return
      showToast(e instanceof Error ? e.message : '预览失败', 'error')
    } finally {
      previewLoading.value = false
    }
}

async function confirmGrantFromPreview() {
  const row = previewCampaign.value
  if (!row) return
  try {
    await ElMessageBox.confirm(
      `确认向以上 ${previewTotal.value} 人发放「${row.name}」礼品券？已持券的人会跳过。`,
      '确认发放',
      { type: 'warning', confirmButtonText: '确认发放', cancelButtonText: '返回核对' },
    )
  } catch {
    return
  }
  previewGranting.value = true
  try {
    const granted = await apiJson(
      `/api/admin/gift-coupons/campaigns/${row.id}/grant?store_id=${storeId.value}`,
      { method: 'POST' },
      { auth: true },
    )
    showToast(`已发放，未核销 ${granted?.granted_count ?? 0} 人`, 'success')
    previewVisible.value = false
    await loadCampaigns()
    selectedId.value = row.id
    entStatus.value = 'granted'
    await loadEntitlements()
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '发放失败', 'error')
  } finally {
    previewGranting.value = false
  }
}

async function closeCamp(row) {
  try {
    await ElMessageBox.confirm('结束后不可再从配送大表核销。未核销名单仍可查看。确定结束？', '结束活动', {
      type: 'warning',
      confirmButtonText: '结束',
      cancelButtonText: '取消',
    })
    await apiJson(
      `/api/admin/gift-coupons/campaigns/${row.id}/close?store_id=${storeId.value}`,
      { method: 'POST' },
      { auth: true },
    )
    showToast('已结束', 'success')
    await loadCampaigns()
    await loadEntitlements()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function revokeRow(row) {
  try {
    await ElMessageBox.confirm(`作废 ${row.member_name || row.member_phone} 的礼品券？`, '作废', {
      type: 'warning',
      confirmButtonText: '作废',
      cancelButtonText: '取消',
    })
    await apiJson(
      `/api/admin/gift-coupons/entitlements/${row.id}/revoke?store_id=${storeId.value}`,
      { method: 'POST' },
      { auth: true },
    )
    showToast('已作废', 'success')
    await loadCampaigns()
    await loadEntitlements()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '作废失败', 'error')
  }
}

async function manualGrant() {
  if (!selectedCampaign.value || selectedCampaign.value.status !== 'active') {
    showToast('请先选择进行中的活动', 'error')
    return
  }
  const phones = String(manualPhones.value || '')
    .split(/[\n,;，；\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  if (!phones.length) {
    showToast('请填写手机号', 'error')
    return
  }
  manualGranting.value = true
  try {
    const data = await apiJson(
      `/api/admin/gift-coupons/entitlements/manual-grant?store_id=${storeId.value}`,
      {
        method: 'POST',
        body: JSON.stringify({ campaign_id: selectedCampaign.value.id, member_phones: phones }),
      },
      { auth: true },
    )
    const ok = Number(data?.success_count) || 0
    const fail = Array.isArray(data?.failed) ? data.failed.length : 0
    showToast(`补发成功 ${ok}，失败 ${fail}`, ok ? 'success' : 'error')
    manualPhones.value = ''
    await loadCampaigns()
    await loadEntitlements()
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '补发失败', 'error')
  } finally {
    manualGranting.value = false
  }
}

onMounted(() => {
  if (!adminAccessToken.value) return
  void loadCampaigns()
})
</script>

<template>
  <div class="gift-coupons-page tab-content animate-up page-content-shell">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="gift-card-head">
          <span>礼品券活动</span>
          <el-button type="primary" @click="openCreate">
            <Plus :size="16" />
            新建活动
          </el-button>
        </div>
      </template>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="礼品券跟餐送给后厨看，不进小程序钱包，也不写入会员备注。发放后到配送大表打印「今日礼品券」标签才会核销。"
        class="gift-alert"
      />
      <el-table v-loading="loading" :data="campaigns" stripe empty-text="暂无活动" highlight-current-row @row-click="selectCampaign">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="sheet_label" label="标签文案" width="110" />
        <el-table-column label="卡型" width="100">
          <template #default="{ row }">{{ planKindsText(row.plan_kinds) }}</template>
        </el-table-column>
        <el-table-column label="入账日" min-width="180">
          <template #default="{ row }">{{ row.credited_from }} ~ {{ row.credited_to }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : row.status === 'closed' ? 'info' : 'warning'" size="small">
              {{ STATUS_CAMP[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="未核销/已核销" width="130">
          <template #default="{ row }">{{ row.granted_count }} / {{ row.redeemed_count }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'draft'" link type="primary" @click.stop="openEdit(row)">编辑</el-button>
            <el-button v-if="row.status !== 'closed'" link type="primary" @click.stop="openPreview(row)">
              {{ row.status === 'draft' ? '查看名单' : '查看补发名单' }}
            </el-button>
            <el-button link type="primary" @click.stop="selectCampaign(row)">未核销名单</el-button>
            <el-button v-if="row.status === 'active'" link type="danger" @click.stop="closeCamp(row)">结束</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="selectedCampaign" shadow="never" class="table-card gift-ent-card">
      <template #header>
        <span>资格明细 · {{ selectedCampaign.name }}</span>
      </template>
      <el-form inline class="gift-ent-filters">
        <el-form-item label="状态">
          <el-select v-model="entStatus" style="width: 120px" @change="entPage = 1; loadEntitlements()">
            <el-option label="未核销" value="granted" />
            <el-option label="已核销" value="redeemed" />
            <el-option label="已作废" value="revoked" />
            <el-option label="全部" value="" />
          </el-select>
        </el-form-item>
        <el-form-item label="手机">
          <el-input v-model="entPhone" clearable placeholder="筛选" style="width: 160px" @keyup.enter="entPage = 1; loadEntitlements()" />
        </el-form-item>
        <el-form-item>
          <el-button @click="entPage = 1; loadEntitlements()">查询</el-button>
        </el-form-item>
      </el-form>
      <div v-if="selectedCampaign.status === 'active'" class="gift-manual">
        <el-input
          v-model="manualPhones"
          type="textarea"
          :rows="2"
          placeholder="手工补发：手机号，逗号或换行分隔"
        />
        <el-button type="primary" :loading="manualGranting" @click="manualGrant">补发</el-button>
      </div>
      <el-table v-loading="entLoading" :data="entitlements" stripe empty-text="暂无记录">
        <el-table-column prop="member_name" label="姓名" min-width="90" />
        <el-table-column prop="member_phone" label="手机" min-width="120" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'granted' ? 'warning' : row.status === 'redeemed' ? 'success' : 'info'" size="small">
              {{ STATUS_ENT[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="granted_at" label="发放时间" min-width="160" />
        <el-table-column prop="redeemed_delivery_date" label="核销业务日" width="120" />
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'granted'" link type="danger" @click="revokeRow(row)">作废</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="gift-pager">
        <el-pagination
          v-model:current-page="entPage"
          v-model:page-size="entPageSize"
          :total="entTotal"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadEntitlements"
          @size-change="entPage = 1; loadEntitlements()"
        />
      </div>
    </el-card>

    <GiftCouponCampaignFormModal
      v-model:visible="formVisible"
      :store-id="storeId"
      :initial="editing"
      @saved="onFormSaved"
    />

    <el-dialog
      v-model="previewVisible"
      :title="previewCampaign ? `圈人名单 · ${previewCampaign.name}` : '圈人名单'"
      width="780px"
      destroy-on-close
    >
      <p class="gift-preview-hint">
        共 <strong>{{ previewTotal }}</strong> 人。请核对姓名和手机后再发放；未出现在此名单的人不会收到礼品券。
      </p>
      <el-table
        v-loading="previewLoading"
        element-loading-text="正在按开卡入账日筛选名单…"
        :data="previewItems"
        max-height="420"
        stripe
        empty-text="没有符合条件的会员（请确认入账日区间，以及是否勾选了月卡/季卡）"
      >
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="name" label="姓名" min-width="100" />
        <el-table-column prop="phone" label="手机" min-width="130" />
        <el-table-column prop="card_kind_label" label="卡种类" width="110" />
        <el-table-column prop="credited_on" label="入账日" width="120" />
      </el-table>
      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
        <el-button
          v-if="previewCampaign && previewCampaign.status !== 'closed'"
          type="primary"
          :loading="previewGranting"
          :disabled="previewLoading || previewTotal < 1"
          @click="confirmGrantFromPreview"
        >
          确认发放
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.gift-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.gift-alert {
  margin-bottom: 12px;
}
.gift-ent-card {
  margin-top: 16px;
}
.gift-ent-filters {
  margin-bottom: 8px;
}
.gift-manual {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 12px;
}
.gift-manual .el-textarea {
  flex: 1;
}
.gift-pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.gift-preview-hint {
  margin: 0 0 12px;
  color: var(--admin-muted, #64748b);
  font-size: 13px;
}
</style>
