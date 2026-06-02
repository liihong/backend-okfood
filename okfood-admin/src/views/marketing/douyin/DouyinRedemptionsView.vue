<script setup>
defineOptions({ name: 'DouyinRedemptionsView' })
import { ref, onMounted } from 'vue'
import { Search } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'

const storeId = ref(1)
const list = ref([])
const loading = ref(false)
const filters = ref({
  member_phone: '',
  status: '',
  date_from: '',
  date_to: '',
})

const STATUS_LABEL = {
  success: '成功',
  failed: '验券失败',
  grant_failed: '发奖失败',
}

const STATUS_TAG = {
  success: 'success',
  failed: 'danger',
  grant_failed: 'warning',
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
  q.set('page', '1')
  q.set('page_size', '50')
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
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function onReset() {
  filters.value = {
    member_phone: '',
    status: '',
    date_from: '',
    date_to: '',
  }
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

      <el-form :inline="true" class="filter-form" @submit.prevent="loadList">
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
            <el-option label="发奖失败" value="grant_failed" />
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
          <el-button type="primary" :loading="loading" @click="loadList">
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
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="member_phone" label="手机号" width="120" />
        <el-table-column prop="member_name" label="姓名" width="90" />
        <el-table-column prop="code_masked" label="券码" width="100" />
        <el-table-column prop="douyin_product_title" label="抖音商品" min-width="120" show-overflow-tooltip />
        <el-table-column label="映射权益" width="110">
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
    </div>
  </section>
</template>

<style scoped>
.filter-form {
  margin-bottom: 16px;
}
</style>
