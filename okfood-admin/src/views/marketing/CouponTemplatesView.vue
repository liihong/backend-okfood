<script setup>
defineOptions({ name: 'CouponTemplatesView' })
import { ref, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import CouponTemplateFormModal from './components/CouponTemplateFormModal.vue'

const storeId = ref(1)
const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref(null)

const BIZ_LABEL = {
  all: '全部小程序',
  member_card: '会员购卡',
  single_meal: '菜单单次零售',
  store_retail: '商城零售',
}

async function loadList() {
  loading.value = true
  try {
    const data = await apiJson(
      `/api/admin/marketing/coupon-templates?store_id=${storeId.value}&page=1&page_size=100`,
      {},
      { auth: true },
    )
    list.value = Array.isArray(data?.items) ? data.items : []
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = row
  dialogVisible.value = true
}

async function onSaved() {
  dialogVisible.value = false
  await loadList()
}

async function toggleActive(row) {
  try {
    await apiJson(
      `/api/admin/marketing/coupon-templates/${row.id}/active?store_id=${storeId.value}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !row.is_active }),
      },
      { auth: true },
    )
    showToast(row.is_active ? '已下架' : '已上架', 'success')
    await loadList()
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

onMounted(() => {
  if (!adminAccessToken.value) return
  void loadList()
})
</script>

<template>
  <section class="tab-content animate-up">
    <div class="table-container">
      <div class="table-header">
        <h2 class="table-title">优惠券券种</h2>
        <button type="button" class="btn-primary" @click="openCreate">
          <Plus :size="18" /> 新建券种
        </button>
      </div>
      <p v-if="loading" class="hint">加载中…</p>
      <el-table v-else :data="list" stripe class="admin-table">
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column label="业务线" width="120">
          <template #default="{ row }">{{ BIZ_LABEL[row.biz_type] || row.biz_type }}</template>
        </el-table-column>
        <el-table-column prop="discount_yuan" label="面额(元)" width="90" />
        <el-table-column prop="min_order_yuan" label="门槛(元)" width="90" />
        <el-table-column label="已发/上限" width="100">
          <template #default="{ row }">
            {{ row.grants_issued }} / {{ row.max_grants != null ? row.max_grants : '∞' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span :class="row.is_active ? 'pill pill--ok' : 'pill pill--muted'">
              {{ row.is_active ? '上架' : '下架' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <button type="button" class="btn-link" @click="openEdit(row)">编辑</button>
            <button type="button" class="btn-link" @click="toggleActive(row)">
              {{ row.is_active ? '下架' : '上架' }}
            </button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <CouponTemplateFormModal
      v-model:visible="dialogVisible"
      :store-id="storeId"
      :initial="editing"
      @saved="onSaved"
    />
  </section>
</template>

<style scoped>
.hint {
  padding: 24px;
  color: var(--admin-muted, #64748b);
}
.pill {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
}
.pill--ok {
  background: #dcfce7;
  color: #166534;
}
.pill--muted {
  background: #f1f5f9;
  color: #64748b;
}
.btn-link {
  background: none;
  border: none;
  color: var(--admin-primary, #0d9488);
  cursor: pointer;
  margin-right: 8px;
  font-size: 13px;
}
</style>
