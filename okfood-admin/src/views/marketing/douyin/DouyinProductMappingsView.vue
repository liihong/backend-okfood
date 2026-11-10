<script setup>
defineOptions({ name: 'DouyinProductMappingsView' })
import { ref, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'
import DouyinProductMappingFormModal from './components/DouyinProductMappingFormModal.vue'

const storeId = ref(1)
const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref(null)

const GRANT_LABEL = {
  week_card: '周卡',
  month_card: '月卡',
  membership_template: '会员卡包',
  coupon_template: '优惠券',
  retail_product: '商城商品',
}

async function loadList() {
  loading.value = true
  try {
    const data = await apiJson(
      `/api/admin/marketing/douyin/product-mappings?store_id=${storeId.value}&page=1&page_size=100`,
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
      `/api/admin/marketing/douyin/product-mappings/${row.id}?store_id=${storeId.value}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !row.is_active }),
      },
      { auth: true },
    )
    showToast(row.is_active ? '已停用' : '已启用', 'success')
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
  <section class="mkt-page tab-content animate-up">
    <header class="mkt-page-head">
      <div class="mkt-page-head__copy">
        <p class="mkt-kicker">小程序营销</p>
        <h1 class="mkt-title">抖音商品设置</h1>
        <p class="mkt-intro">
          把抖音来客商品 ID 和本地权益关联。用户验券成功后，按映射发放周卡、月卡、卡包、优惠券，或生成商城订单。
        </p>
      </div>
      <el-button type="primary" round size="large" @click="openCreate">
        <Plus :size="16" />
        新建映射
      </el-button>
    </header>

    <article class="mkt-card">
      <header class="mkt-card__head">
        <span class="mkt-card__title">商品映射</span>
        <span class="mkt-card__hint">停用后不再按该商品发奖</span>
      </header>
      <div class="mkt-table-wrap">
        <el-table v-loading="loading" :data="list" class="admin-table" empty-text="暂无映射，请点击右上角新建">
          <el-table-column prop="display_name" label="名称" min-width="120" />
          <el-table-column prop="douyin_product_id" label="product_id" min-width="100" show-overflow-tooltip />
          <el-table-column prop="douyin_sku_id" label="sku_id" min-width="100" show-overflow-tooltip />
          <el-table-column prop="douyin_product_out_id" label="product_out_id" min-width="110" show-overflow-tooltip />
          <el-table-column label="映射类型" width="110">
            <template #default="{ row }">
              <el-tag round effect="light">{{ GRANT_LABEL[row.grant_type] || row.grant_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="关联目标" width="100">
            <template #default="{ row }">
              {{ row.target_id != null ? `#${row.target_id}` : '—' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="96">
            <template #default="{ row }">
              <el-tag round effect="light" :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="primary" @click="toggleActive(row)">
                {{ row.is_active ? '停用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </article>

    <DouyinProductMappingFormModal
      v-model:visible="dialogVisible"
      :store-id="storeId"
      :initial="editing"
      @saved="onSaved"
    />
  </section>
</template>

