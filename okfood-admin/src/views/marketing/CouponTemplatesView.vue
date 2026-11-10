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
  <section class="mkt-page tab-content animate-up">
    <header class="mkt-page-head">
      <div class="mkt-page-head__copy">
        <p class="mkt-kicker">小程序营销</p>
        <h1 class="mkt-title">优惠券管理</h1>
        <p class="mkt-intro">配置小程序代金券券种、面额、门槛和适用范围。下架后不再新发，已发出的券仍按原规则使用。</p>
      </div>
      <el-button type="primary" round size="large" @click="openCreate">
        <Plus :size="16" />
        新建券种
      </el-button>
    </header>

    <article class="mkt-card">
      <header class="mkt-card__head">
        <span class="mkt-card__title">券种列表</span>
        <span class="mkt-card__hint">已发数量达到上限后停止发放</span>
      </header>
      <div class="mkt-table-wrap">
        <el-table v-loading="loading" :data="list" class="admin-table" empty-text="暂无券种">
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column label="业务线" width="140">
            <template #default="{ row }">{{ BIZ_LABEL[row.biz_type] || row.biz_type }}</template>
          </el-table-column>
          <el-table-column prop="discount_yuan" label="面额(元)" width="100" />
          <el-table-column prop="min_order_yuan" label="门槛(元)" width="100" />
          <el-table-column label="已发/上限" width="110">
            <template #default="{ row }">
              {{ row.grants_issued }} / {{ row.max_grants != null ? row.max_grants : '∞' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="96">
            <template #default="{ row }">
              <el-tag round effect="light" :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? '上架' : '下架' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="primary" @click="toggleActive(row)">
                {{ row.is_active ? '下架' : '上架' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </article>

    <CouponTemplateFormModal
      v-model:visible="dialogVisible"
      :store-id="storeId"
      :initial="editing"
      @saved="onSaved"
    />
  </section>
</template>
