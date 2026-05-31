<script setup>
defineOptions({ name: 'MemberCouponGrantsView' })
import { ref, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import GrantCouponModal from './components/GrantCouponModal.vue'

const storeId = ref(1)
const list = ref([])
const loading = ref(false)
const grantVisible = ref(false)

const STATUS_LABEL = {
  available: '待使用',
  locked: '已锁定',
  used: '已使用',
  revoked: '已作废',
  expired: '已过期',
}

async function loadList() {
  loading.value = true
  try {
    const data = await apiJson(
      `/api/admin/marketing/member-coupons?store_id=${storeId.value}&page=1&page_size=100`,
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

async function revokeRow(row) {
  if (row.status !== 'available') return
  if (!window.confirm(`确定作废优惠券 #${row.id}？`)) return
  try {
    await apiJson(
      `/api/admin/marketing/member-coupons/${row.id}/revoke?store_id=${storeId.value}`,
      { method: 'POST', body: '{}' },
      { auth: true },
    )
    showToast('已作废', 'success')
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
        <h2 class="table-title">优惠券发放记录</h2>
        <button type="button" class="btn-primary" @click="grantVisible = true">
          <Plus :size="18" /> 发放优惠券
        </button>
      </div>
      <p v-if="loading" class="hint">加载中…</p>
      <el-table v-else :data="list" stripe class="admin-table">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="template_name" label="券种" min-width="120" />
        <el-table-column label="会员" min-width="140">
          <template #default="{ row }">
            {{ row.member_name || '—' }} / {{ row.member_phone || row.member_id }}
          </template>
        </el-table-column>
        <el-table-column prop="discount_yuan" label="面额" width="80" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">{{ STATUS_LABEL[row.status] || row.status }}</template>
        </el-table-column>
        <el-table-column prop="expires_at" label="过期时间" min-width="160" />
        <el-table-column prop="issued_by" label="发放人" width="100" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <button
              v-if="row.status === 'available'"
              type="button"
              class="btn-link"
              @click="revokeRow(row)"
            >
              作废
            </button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <GrantCouponModal v-model:visible="grantVisible" :store-id="storeId" @saved="loadList" />
  </section>
</template>

<style scoped>
.hint {
  padding: 24px;
  color: var(--admin-muted, #64748b);
}
.btn-link {
  background: none;
  border: none;
  color: #dc2626;
  cursor: pointer;
  font-size: 13px;
}
</style>
