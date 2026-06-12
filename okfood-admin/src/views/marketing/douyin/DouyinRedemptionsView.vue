<script setup>
defineOptions({ name: 'DouyinRedemptionsView' })
import { ref, onMounted } from 'vue'
import { Search } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'

const storeId = ref(1)
const list = ref([])
const loading = ref(false)
/** 分页：与接口 page / page_size 一致 */
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const pageSizeOptions = [10, 20, 50, 100]
const filters = ref({
  member_phone: '',
  status: '',
  date_from: '',
  date_to: '',
})

const STATUS_LABEL = {
  success: '成功',
  failed: '验券失败',
  verified: '已核销待发奖',
  grant_failed: '发奖失败',
  cancelled: '已撤销',
}

const STATUS_TAG = {
  success: 'success',
  failed: 'danger',
  verified: 'warning',
  grant_failed: 'warning',
  cancelled: 'info',
}

const GRANT_LABEL = {
  week_card: '周卡',
  month_card: '月卡',
  membership_template: '会员卡包',
  coupon_template: '优惠券',
}

function buildQuery() {
  const q = new URLSearchParams()
  q.set('store_id', String(storeId.value))
  q.set('page', String(page.value))
  q.set('page_size', String(pageSize.value))
  const ph = filters.value.member_phone.trim()
  if (ph) q.set('member_phone', ph)
  if (filters.value.status) q.set('status', filters.value.status)
  if (filters.value.date_from) q.set('date_from', filters.value.date_from)
  if (filters.value.date_to) q.set('date_to', filters.value.date_to)
  return q.toString()
}

async function loadList() {
  loading.value = true
  try {
    const data = await apiJson(
      `/api/admin/marketing/douyin/redemptions?${buildQuery()}`,
      {},
      { auth: true },
    )
    list.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total) || 0
    // 筛选后当前页可能已无数据，自动回退一页
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

function onSearch() {
  page.value = 1
  void loadList()
}

function onReset() {
  filters.value = {
    member_phone: '',
    status: '',
    date_from: '',
    date_to: '',
  }
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

onMounted(() => {
  if (!adminAccessToken.value) return
  void loadList()
})
</script>

<template>
  <section class="tab-content animate-up">
    <div class="table-container">
      <div class="table-header">
        <h2 class="table-title">抖音核销记录</h2>
      </div>

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
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 140px">
            <el-option label="成功" value="success" />
            <el-option label="验券失败" value="failed" />
            <el-option label="已核销待发奖" value="verified" />
            <el-option label="发奖失败" value="grant_failed" />
            <el-option label="已撤销" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="filters.date_from"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 150px"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="filters.date_to"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 150px"
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

      <el-table
        v-loading="loading"
        :data="list"
        stripe
        class="admin-table"
        empty-text="暂无核销记录"
      >
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column prop="member_phone" label="手机号" width="120" />
        <el-table-column prop="member_name" label="姓名" width="90" />
        <el-table-column prop="code_masked" label="券码" width="150" />
        <el-table-column prop="douyin_product_title" label="抖音商品" min-width="150" show-overflow-tooltip />
        <el-table-column label="映射权益" width="130">
          <template #default="{ row }">
            {{ row.mapping_display_name || GRANT_LABEL[row.grant_type] || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="STATUS_TAG[row.status] || 'info'">
              {{ STATUS_LABEL[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_msg" label="备注" min-width="140" show-overflow-tooltip />
        <el-table-column prop="douyin_order_id" label="抖音订单号" min-width="140" show-overflow-tooltip />
      </el-table>
      <div v-if="adminAccessToken" class="douyin-redemptions-pagination">
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
  </section>
</template>

<style scoped>
.filter-form {
  margin-bottom: 16px;
}
.douyin-redemptions-pagination {
  display: flex;
  justify-content: flex-end;
  padding: 1.25rem 2rem;
  border-top: 1px solid #f8fafc;
  background: #fafafa;
}
</style>
