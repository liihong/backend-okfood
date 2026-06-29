<script setup>
defineOptions({ name: 'MemberCouponGrantsView' })
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, Search } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import GrantCouponModal from './components/GrantCouponModal.vue'

const route = useRoute()
const router = useRouter()

const storeId = ref(1)
const list = ref([])
const loading = ref(false)
const grantVisible = ref(false)
/** 打开发券弹窗时的预填（来自会员统计/档案跳转） */
const grantPrefill = ref({
  mode: 'single',
  phone: '',
  phonesText: '',
  remark: '',
})
/** 分页：与接口 page / page_size 一致 */
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const pageSizeOptions = [10, 20, 50, 100]
const filters = ref({
  member_phone: '',
})

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
    const q = new URLSearchParams()
    q.set('store_id', String(storeId.value))
    q.set('page', String(page.value))
    q.set('page_size', String(pageSize.value))
    const ph = filters.value.member_phone.trim()
    if (ph) q.set('member_phone', ph)
    const data = await apiJson(`/api/admin/marketing/member-coupons?${q.toString()}`, {}, { auth: true })
    list.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total) || 0
    // 作废等操作后，当前页可能已无数据，自动回退一页
    if (list.value.length === 0 && page.value > 1) {
      page.value -= 1
      return await loadList()
    }
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

/** 拉取全部待续费会员手机号（分页合并，供批量发券预填） */
async function fetchRenewPendingPhonesText() {
  const phones = []
  const seen = new Set()
  let pageNum = 1
  const ps = 100
  for (;;) {
    const q = new URLSearchParams({
      page: String(pageNum),
      page_size: String(ps),
      renew_pending_only: '1',
    })
    const data = await apiJson(`/api/admin/users?${q.toString()}`, {}, { auth: true })
    const items = Array.isArray(data?.items) ? data.items : []
    for (const it of items) {
      const ph = String(it.phone || '').trim()
      if (!ph || seen.has(ph)) continue
      seen.add(ph)
      phones.push(ph)
    }
    const totalCount = Number(data?.total) || 0
    if (pageNum * ps >= totalCount || items.length < ps) break
    pageNum += 1
  }
  return phones.join('\n')
}

function resetGrantPrefill() {
  grantPrefill.value = { mode: 'single', phone: '', phonesText: '', remark: '' }
}

function openGrantModal() {
  resetGrantPrefill()
  grantVisible.value = true
}

/** 会员统计/档案页带 query 跳转时自动打开发券弹窗 */
async function tryOpenGrantFromRouteQuery() {
  if (String(route.query.grant || '') !== '1') return
  const batch = String(route.query.batch || '').trim()
  const phone = String(route.query.phone || '').trim().replace(/\s+/g, '').replace(/-/g, '')

  if (batch === 'renew_pending') {
    const phonesText = await fetchRenewPendingPhonesText()
    if (!phonesText) {
      showToast('暂无待续费会员', 'info')
    } else {
      grantPrefill.value = {
        mode: 'batch',
        phone: '',
        phonesText,
        remark: '待续费会员续卡激励',
      }
      grantVisible.value = true
    }
  } else if (phone) {
    grantPrefill.value = {
      mode: 'single',
      phone,
      phonesText: '',
      remark: '',
    }
    grantVisible.value = true
  }

  const nextQuery = { ...route.query }
  delete nextQuery.grant
  delete nextQuery.batch
  delete nextQuery.phone
  router.replace({ path: route.path, query: nextQuery })
}

function onSearch() {
  page.value = 1
  void loadList()
}

function onReset() {
  filters.value.member_phone = ''
  page.value = 1
  void loadList()
}

function onPageChange(nextPage) {
  page.value = nextPage
  void loadList()
}

function onPageSizeChange(nextSize) {
  pageSize.value = nextSize
  page.value = 1
  void loadList()
}

function onGrantSaved() {
  page.value = 1
  void loadList()
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

onMounted(async () => {
  if (!adminAccessToken.value) return
  await loadList()
  await tryOpenGrantFromRouteQuery()
})
</script>

<template>
  <section class="tab-content animate-up">
    <div class="table-container">
      <div class="table-header">
        <h2 class="table-title">优惠券发放记录</h2>
      </div>

      <div class="coupon-grants-toolbar">
        <el-form :inline="true" class="filter-form" @submit.prevent="onSearch">
          <el-form-item label="手机号">
            <el-input
              v-model="filters.member_phone"
              placeholder="会员手机号"
              clearable
              maxlength="20"
              style="width: 160px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="onSearch">
              <Search :size="16" style="margin-right: 4px" />
              查询
            </el-button>
            <el-button @click="onReset">重置</el-button>
          </el-form-item>
        </el-form>
        <button type="button" class="btn-primary btn-primary--sm" @click="openGrantModal">
          <Plus :size="16" /> 发放优惠券
        </button>
      </div>

      <el-table
        v-loading="loading"
        :data="list"
        stripe
        class="admin-table"
        empty-text="暂无发放记录"
      >
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
      <div v-if="adminAccessToken" class="coupon-grants-pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="pageSizeOptions"
          :disabled="loading"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </div>
    <GrantCouponModal
      v-model:visible="grantVisible"
      :store-id="storeId"
      :initial-grant-mode="grantPrefill.mode"
      :initial-member-phone="grantPrefill.phone"
      :initial-member-phones-text="grantPrefill.phonesText"
      :initial-remark="grantPrefill.remark"
      @saved="onGrantSaved"
    />
  </section>
</template>

<style scoped>
.coupon-grants-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.filter-form {
  margin-bottom: 0;
  flex: 1;
}
.coupon-grants-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 1.25rem 2rem;
  border-top: 1px solid #f8fafc;
  background: #fafafa;
}
.btn-link {
  background: none;
  border: none;
  color: #dc2626;
  cursor: pointer;
  font-size: 13px;
}
</style>
