<script setup>
import { computed, onMounted, ref } from 'vue'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const DAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const loading = ref(false)
const savingSlot = ref(null)
const preview = ref(null)
const dishes = ref([])

const dishOptions = computed(() =>
  (dishes.value || []).map((d) => {
    const priceStr =
      d.single_order_price_yuan != null && String(d.single_order_price_yuan).trim() !== ''
        ? `¥${String(d.single_order_price_yuan).trim()}`
        : ''
    const priceHint = priceStr ? `（${priceStr}）` : '（未定价，会员端显示待公布）'
    return {
      value: d.id,
      label: d.is_enabled === false ? `${d.name}（已停用）` : `${d.name}${priceHint}`,
      disabled: d.is_enabled === false,
    }
  }),
)

function slotsToRows(slotList, weekStartIso) {
  const bySlot = Object.fromEntries((slotList || []).map((s) => [s.slot, s]))
  return [1, 2, 3, 4, 5, 6, 7].map((slot) => ({
    slot,
    weekday: DAY_LABELS[slot - 1],
    weekStart: weekStartIso,
    dish_id: bySlot[slot]?.dish_id ?? null,
    name: bySlot[slot]?.name ?? '',
    single_order_price_yuan: bySlot[slot]?.single_order_price_yuan ?? null,
  }))
}

/** @param {unknown} v */
function formatSlotPriceHint(v) {
  if (v == null) return '—'
  const s = String(v).trim()
  return s !== '' ? `¥${s}` : '—'
}

const thisWeekRows = computed(() => {
  const p = preview.value
  if (!p || !p.this_week_start) return []
  return slotsToRows(p.this_week, p.this_week_start)
})

const nextWeekRows = computed(() => {
  const p = preview.value
  if (!p || !p.next_week_start) return []
  return slotsToRows(p.next_week, p.next_week_start)
})

async function fetchDishes() {
  if (!adminAccessToken.value) return
  try {
    const data = await apiJson('/api/admin/dishes', {}, { auth: true })
    dishes.value = Array.isArray(data) ? data : []
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载菜品失败', 'error')
  }
}

async function loadPreview() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    preview.value = await apiJson('/api/admin/menu/weekly-slots', {}, { auth: true })
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载周菜单失败', 'error')
    preview.value = null
  } finally {
    loading.value = false
  }
}

async function onDishChange(row, dishId) {
  const key = `${row.weekStart}-${row.slot}`
  savingSlot.value = key
  try {
    await apiJson(
      '/api/admin/menu/weekly-slot',
      {
        method: 'POST',
        body: JSON.stringify({
          week_start: row.weekStart,
          slot: row.slot,
          dish_id: dishId == null || dishId === '' ? null : Number(dishId),
        }),
      },
      { auth: true },
    )
    showToast('槽位已保存', 'success')
    await loadPreview()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
    await loadPreview()
  } finally {
    savingSlot.value = null
  }
}

onMounted(() => {
  void fetchDishes()
  void loadPreview()
})
</script>

<template>
  <section class="tab-content animate-up weekly-menu-page">
    <p class="weekly-intro">
      维护每周一至周日的固定槽位菜品；与按日排期共用「同一自然月内同一道菜仅出现一次」规则。
    </p>

    <div v-loading="loading" class="weekly-cards">
      <el-card v-if="preview" class="weekly-card" shadow="never">
        <template #header>
          <div class="card-head">
            <span>本周</span>
            <el-tag type="success" effect="plain" round>起：{{ preview.this_week_start }}</el-tag>
          </div>
        </template>
        <el-table :data="thisWeekRows" stripe border class="weekly-table">
          <el-table-column prop="weekday" label="星期" width="88" />
          <el-table-column label="单点价" width="100">
            <template #default="{ row }">
              <span
                :class="
                  row.dish_id && (!row.single_order_price_yuan || !String(row.single_order_price_yuan).trim())
                    ? 'weekly-price-missing'
                    : ''
                "
              >
                {{
                  row.dish_id
                    ? formatSlotPriceHint(row.single_order_price_yuan)
                    : '—'
                }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="菜品">
            <template #default="{ row }">
              <el-select
                :model-value="row.dish_id"
                filterable
                clearable
                placeholder="选择菜品"
                class="weekly-select"
                :loading="savingSlot === `${row.weekStart}-${row.slot}`"
                @update:model-value="(v) => onDishChange(row, v)"
              >
                <el-option
                  v-for="opt in dishOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                  :disabled="opt.disabled"
                />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="preview" class="weekly-card" shadow="never">
        <template #header>
          <div class="card-head">
            <span>下周</span>
            <el-tag type="info" effect="plain" round>起：{{ preview.next_week_start }}</el-tag>
          </div>
        </template>
        <el-table :data="nextWeekRows" stripe border class="weekly-table">
          <el-table-column prop="weekday" label="星期" width="88" />
          <el-table-column label="单点价" width="100">
            <template #default="{ row }">
              <span
                :class="
                  row.dish_id && (!row.single_order_price_yuan || !String(row.single_order_price_yuan).trim())
                    ? 'weekly-price-missing'
                    : ''
                "
              >
                {{
                  row.dish_id
                    ? formatSlotPriceHint(row.single_order_price_yuan)
                    : '—'
                }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="菜品">
            <template #default="{ row }">
              <el-select
                :model-value="row.dish_id"
                filterable
                clearable
                placeholder="选择菜品"
                class="weekly-select"
                :loading="savingSlot === `${row.weekStart}-${row.slot}`"
                @update:model-value="(v) => onDishChange(row, v)"
              >
                <el-option
                  v-for="opt in dishOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                  :disabled="opt.disabled"
                />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </section>
</template>

<style scoped>
.weekly-menu-page .weekly-intro {
  margin: 0 0 1.25rem;
  font-size: 0.9375rem;
  color: #64748b;
  line-height: 1.5;
}

.weekly-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.25rem;
}

.weekly-card {
  border-radius: 12px;
  border: 1px solid var(--el-border-color-lighter);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.weekly-table {
  width: 100%;
}

.weekly-select {
  width: 100%;
  min-width: 0;
}

.weekly-price-missing {
  color: var(--el-color-danger);
  font-weight: 600;
}
</style>
