<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { Printer, RefreshCw, MapPin } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

/** 与后端业务日一致：Asia/Shanghai 的日历日期 YYYY-MM-DD */
function ymdInTimeZone(date, timeZone) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const map = Object.fromEntries(parts.filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]))
  return `${map.year}-${map.month}-${map.day}`
}

function todayShanghaiStr() {
  return ymdInTimeZone(new Date(), 'Asia/Shanghai')
}

const emptySheet = () => ({ delivery_date: '', groups: [], active_regions: [] })

const areaFilter = ref('')
/** 查询用的配送业务日（上海日历日 YYYY-MM-DD），可与「今天」不同 */
const deliveryDateQuery = ref(todayShanghaiStr())
/** 与后端 delivery_regions 启用列表同源（来自 delivery-sheet 响应） */
const activeRegions = ref([])
const sheetToday = ref(emptySheet())
const loading = ref(false)

/** 当前选中的路由分组片区（与 group.area 一致） */
const activeRegionTab = ref('')

function syncDeliveryRegionTabs() {
  const gt = sheetToday.value.groups || []
  const namesT = gt.map((g) => g.area)
  if (!namesT.length) {
    activeRegionTab.value = ''
  } else if (!namesT.includes(activeRegionTab.value)) {
    activeRegionTab.value = namesT[0]
  }
}

const selectedGroup = computed(() => {
  const groups = sheetToday.value.groups || []
  if (!groups.length) return null
  const cur = activeRegionTab.value
  return groups.find((g) => g.area === cur) || groups[0]
})

function countIssueStops(sheet) {
  let n = 0
  for (const g of sheet.groups || []) {
    for (const st of g.stops || []) {
      if (st.has_area_issue) n += 1
    }
  }
  return n
}

const sheetIssueStopCount = computed(() => countIssueStops(sheetToday.value))

function flatStopsForSheet(sheet) {
  const out = []
  for (const g of sheet.groups || []) {
    let idx = 0
    for (const st of g.stops || []) {
      idx += 1
      out.push({
        groupArea: g.area,
        stopIndex: idx,
        ...st,
      })
    }
  }
  return out
}

const flatStops = computed(() => flatStopsForSheet(sheetToday.value))

/** 配送点行高亮：片区待维护 */
function deliveryStopRowClassName({ row }) {
  return row.has_area_issue ? 'delivery-row--area-warn' : ''
}

async function fetchSheet() {
  if (!adminAccessToken.value) return
  loading.value = true
  const d0 = (deliveryDateQuery.value || '').trim() || todayShanghaiStr()
  try {
    const base = new URLSearchParams()
    const a = (areaFilter.value || '').trim()
    if (a) base.set('area', a)

    const q0 = new URLSearchParams(base)
    q0.set('delivery_date', d0)

    const data0 = await apiJson(`/api/admin/delivery-sheet?${q0.toString()}`, {}, { auth: true })

    const regions0 = Array.isArray(data0?.active_regions) ? data0.active_regions : []
    activeRegions.value = regions0

    const resolvedDate = data0?.delivery_date || d0
    if (data0?.delivery_date) deliveryDateQuery.value = data0.delivery_date
    sheetToday.value = {
      delivery_date: resolvedDate,
      groups: Array.isArray(data0?.groups) ? data0.groups : [],
      active_regions: regions0,
    }
    syncDeliveryRegionTabs()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    sheetToday.value = emptySheet()
    activeRegionTab.value = ''
    activeRegions.value = []
    showToast(e instanceof Error ? e.message : '加载配送表失败', 'error')
  } finally {
    loading.value = false
  }
}

async function printLabels() {
  if (!flatStops.value.length) {
    showToast('没有可打印的配送点', 'error')
    return
  }
  await nextTick()
  window.print()
}

/** 标签用：仅姓名，顿号分隔（不印电话、地址） */
function labelNamesText(st) {
  const names = (st.members || []).map((m) => (m.name || '').trim()).filter(Boolean)
  return names.length ? names.join('、') : '—'
}

watch(adminAccessToken, (t) => {
  if (t) fetchSheet()
})

onMounted(() => {
  if (adminAccessToken.value) fetchSheet()
})
</script>

<template>
  <section class="tab-content animate-up delivery-view">
    <div class="delivery-toolbar no-print">
      <!-- 单行：左日期/片区，右统计文案 + 刷新/打印 -->
      <div class="delivery-toolbar__row delivery-toolbar__row--primary">
        <div class="delivery-toolbar__filters">
          <label class="delivery-field">
            <span>配送业务日（上海）</span>
            <el-date-picker
              v-model="deliveryDateQuery"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              :disabled="loading"
              :clearable="true"
              class="delivery-el-date"
              @change="fetchSheet"
            />
          </label>
          <label class="delivery-field">
            <span>片区</span>
            <el-select
              v-model="areaFilter"
              placeholder="全部"
              clearable
              :disabled="loading"
              class="delivery-el-select"
              @change="fetchSheet"
            >
              <el-option label="全部" value="" />
              <el-option v-for="n in activeRegions" :key="n" :label="n" :value="n" />
            </el-select>
          </label>
        </div>
        <div class="delivery-toolbar__actions">
          <p class="delivery-meta">
            共 <strong>{{ flatStops.length }}</strong> 个配送点 ·
            <strong>{{ flatStops.reduce((s, x) => s + (x.meal_count || 0), 0) }}</strong>
            份（已排除请假区间覆盖该业务日、以及「明天请假」命中该日的会员）
          </p>
          <button type="button" class="btn-ghost delivery-icon-btn" :disabled="loading" @click="fetchSheet">
            <RefreshCw :size="18" :class="{ 'spin': loading }" />
            刷新
          </button>
          <button
            type="button"
            class="btn-primary delivery-print-btn"
            :disabled="loading || !flatStops.length"
            @click="printLabels"
          >
            <Printer :size="18" />
            打印标签
          </button>
        </div>
      </div>
      <!-- 片区统计与切换：单独一行，右对齐，不占表格区 -->
      <div
        v-if="!loading && sheetToday.groups?.length"
        class="delivery-toolbar__region-tabs"
      >
        <div class="delivery-tablist" role="tablist" aria-label="配送片区">
          <button
            v-for="group in sheetToday.groups"
            :key="'t-tab-' + group.area"
            type="button"
            role="tab"
            class="delivery-region-tab"
            :class="{
              'delivery-region-tab--active': activeRegionTab === group.area,
              'delivery-region-tab--warn': group.has_area_issue,
            }"
            :aria-selected="activeRegionTab === group.area"
            @click="activeRegionTab = group.area"
          >
            <span class="delivery-region-tab__label">{{ group.area }}</span>
            <span class="delivery-region-tab__meta">{{ group.meal_total }} 份 · {{ group.stop_count }} 点</span>
          </button>
        </div>
      </div>
    </div>

    <p v-if="loading" class="members-loading no-print">加载中…</p>

    <template v-else>
      <div class="delivery-main no-print">
        <section class="delivery-day-block">
          <h3 class="delivery-day-title">
            <MapPin :size="20" class="inline-icon" />
            配送列表
            <span class="delivery-day-date">{{ sheetToday.delivery_date }}</span>
          </h3>
          <p v-if="sheetIssueStopCount > 0" class="delivery-area-alert delivery-area-alert--compact">
            有
            <strong>{{ sheetIssueStopCount }}</strong>
            个配送点需维护片区，见下表标注。
          </p>
          <p v-if="!sheetToday.groups?.length" class="members-loading">当日暂无待配送记录（或已全部请假/未激活/无余额）。</p>
          <div v-else class="delivery-region-tabs">
            <div v-if="selectedGroup" role="tabpanel" :aria-label="selectedGroup.area" class="delivery-tabpanel">
              <div class="group-card">
                <div class="group-header" :class="{ 'group-header--area-warn': selectedGroup.has_area_issue }">
                  <h4>
                    <MapPin :size="18" class="inline-icon" />
                    {{ selectedGroup.area }}
                    <span v-if="selectedGroup.has_area_issue" class="group-area-badge">区域待维护</span>
                  </h4>
                  <span class="badge">{{ selectedGroup.meal_total }} 份 · {{ selectedGroup.stop_count }} 点</span>
                </div>
                <div class="group-card__table-scroll">
                <AdminTable
                  variant="delivery"
                  :data="selectedGroup.stops"
                  :row-class-name="deliveryStopRowClassName"
                  :stripe="false"
                  empty-text="暂无配送点"
                >
                  <el-table-column label="序号" width="80" min-width="80" class-name="col-idx">
                    <template #default="{ $index }">
                      <span class="t-idx">{{ $index + 1 }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="餐数" width="100" min-width="100" class-name="col-meals">
                    <template #default="{ row: st }">
                      <span class="meal-pill">{{ st.meal_count }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="收件地址" min-width="200" class-name="col-addr">
                    <template #default="{ row: st }">
                      <span class="t-addr">{{ st.address_line }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="联系人" min-width="200" class-name="col-contact">
                    <template #default="{ row: st }">
                      <div
                        v-for="(m, mi) in st.members"
                        :key="m.phone + mi"
                        class="contact-line"
                        :class="{ 'contact-line--area-warn': m.area_issue }"
                      >
                        <span class="t-name">{{ m.name }}</span>
                        <span v-if="m.area_issue" class="member-area-tag">未分配片区</span>
                        <span class="t-sub">{{ m.phone }}</span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="备注" min-width="120" class-name="col-rmk">
                    <template #default="{ row: st }">
                      <span v-if="st.remarks_combined" class="remark-tag">{{ st.remarks_combined }}</span>
                      <span v-else class="empty-text">无</span>
                    </template>
                  </el-table-column>
                </AdminTable>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>

    <!-- 仅用于打印：每配送点一页；不含电话与门牌等地址敏感信息 -->
    <div class="label-print-root">
      <div v-for="(st, li) in flatStops" :key="'lbl-' + li + st.address_line" class="label-page">
        <div class="label-sheet">
          <div class="label-names">{{ labelNamesText(st) }}</div>
          <div class="label-area">区域 {{ st.groupArea }}</div>
          <div class="label-meal-line">{{ st.meal_count }} 份</div>
          <div v-if="st.remarks_combined" class="label-rmk">{{ st.remarks_combined }}</div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.delivery-toolbar {
  margin-bottom: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
/* 顶栏首行：左日期/片区，右统计 + 按钮 */
.delivery-toolbar__row--primary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem 1rem;
}
.delivery-toolbar__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem;
  flex: 0 1 auto;
  min-width: 0;
}
.delivery-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem 1rem;
  flex: 1 1 auto;
  min-width: 0;
}
.delivery-toolbar__region-tabs {
  display: flex;
  justify-content: flex-end;
}
.delivery-toolbar__region-tabs .delivery-tablist {
  justify-content: flex-end;
  max-width: 100%;
}
.delivery-main {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.delivery-day-block {
  padding-top: 0.5rem;
  border-top: 1px solid #e2e8f0;
}
.delivery-day-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem 0.5rem;
  margin: 0 0 0.75rem;
  font-size: 1.05rem;
  font-weight: 900;
  color: #0f172a;
}
.delivery-day-date {
  font-size: 0.85rem;
  font-weight: 700;
  color: #64748b;
}
.delivery-area-alert--compact {
  margin: 0 0 0.75rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.75rem;
}

.delivery-region-tabs {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.delivery-tablist {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: stretch;
}
.delivery-region-tab {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.2rem;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475569;
  font: inherit;
  padding: 0.45rem 0.9rem;
  border-radius: 0.75rem;
  cursor: pointer;
  text-align: left;
  transition:
    background 0.2s,
    color 0.2s,
    border-color 0.2s,
    box-shadow 0.2s;
  max-width: 100%;
}
.delivery-region-tab:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}
.delivery-region-tab--active {
  background: #0e5a44;
  color: #fff;
  border-color: #0e5a44;
  box-shadow: 0 1px 3px rgba(14, 90, 68, 0.35);
}
.delivery-region-tab--active .delivery-region-tab__meta {
  color: rgba(255, 255, 255, 0.85);
}
.delivery-region-tab--warn:not(.delivery-region-tab--active) {
  border-color: #fdba74;
  background: #fffbeb;
}
.delivery-region-tab--warn.delivery-region-tab--active {
  box-shadow:
    0 0 0 2px #fff,
    0 0 0 4px #fb923c;
}
.delivery-region-tab__label {
  font-size: 0.8rem;
  font-weight: 900;
  line-height: 1.2;
  word-break: break-all;
}
.delivery-region-tab__meta {
  font-size: 0.65rem;
  font-weight: 700;
  color: #64748b;
}
.delivery-tabpanel {
  min-width: 0;
}

.delivery-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
}
/* Element Plus：与原先原生控件宽度、圆角风格接近 */
.delivery-field :deep(.delivery-el-date) {
  width: 11rem;
  max-width: 100%;
}
.delivery-field :deep(.delivery-el-date .el-input__wrapper) {
  border-radius: 0.75rem;
}
.delivery-field :deep(.delivery-el-select) {
  width: 11rem;
  max-width: 100%;
}
.delivery-field :deep(.delivery-el-select .el-select__wrapper) {
  border-radius: 0.75rem;
}
.delivery-icon-btn,
.delivery-print-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 999px;
  font-weight: 700;
  font-size: 0.8rem;
  cursor: pointer;
  border: none;
}
.delivery-icon-btn {
  background: #f1f5f9;
  color: #475569;
}
.delivery-print-btn {
  background: #0e5a44;
  color: white;
}
.delivery-print-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.spin {
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.delivery-meta {
  margin: 0;
  font-size: 0.8rem;
  color: #64748b;
  text-align: right;
  line-height: 1.4;
  flex: 1 1 14rem;
  min-width: min(100%, 12rem);
}
.inline-icon {
  vertical-align: -0.2em;
  margin-right: 0.25rem;
}
.col-contact {
  min-width: 10rem;
}
.contact-line {
  margin-bottom: 0.35rem;
}
.contact-line:last-child {
  margin-bottom: 0;
}
.meal-pill {
  display: inline-block;
  min-width: 2rem;
  text-align: center;
  font-weight: 900;
  font-size: 1.1rem;
  color: #0e5a44;
  background: #d1fae5;
  padding: 0.2rem 0.5rem;
  border-radius: 0.5rem;
  white-space: nowrap;
  box-sizing: border-box;
}
.t-contact {
  font-size: 0.8rem;
  vertical-align: top;
}

.delivery-area-alert {
  margin: 0.75rem 0 0;
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  background: #fff7ed;
  border: 1px solid #fdba74;
  color: #9a3412;
  font-size: 0.8rem;
  line-height: 1.45;
}

.group-header--area-warn {
  background: linear-gradient(90deg, rgba(251, 146, 60, 0.2), transparent);
}

.group-area-badge {
  margin-left: 0.5rem;
  font-size: 12px;
  font-weight: 900;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fed7aa;
  color: #9a3412;
  vertical-align: middle;
}

.contact-line--area-warn .t-name {
  color: #c2410c;
}

.member-area-tag {
  display: inline-block;
  margin: 0 0.35rem;
  font-size: 9px;
  font-weight: 900;
  padding: 2px 6px;
  border-radius: 4px;
  background: #ffedd5;
  color: #c2410c;
  vertical-align: middle;
}
</style>

<style>
/* 全局打印：隐藏侧栏与顶栏，仅输出标签区域 */
@media print {
  .admin-layout .sidebar,
  .admin-layout .top-header,
  .admin-layout .modal-overlay {
    display: none !important;
  }
  .admin-layout .main-body {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    max-width: none !important;
  }
  .no-print {
    display: none !important;
  }
}

@page {
  size: 50mm 40mm;
  margin: 2mm;
}

.label-print-root {
  display: none;
}

@media print {
  .label-print-root {
    display: block !important;
  }
}

.label-page {
  page-break-after: always;
  break-after: page;
  width: 50mm;
  height: 40mm;
  box-sizing: border-box;
}

.label-page:last-child {
  page-break-after: auto;
  break-after: auto;
}

.label-sheet {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  border: 0.3mm solid #333;
  padding: 2mm 2.5mm;
  font-family: system-ui, 'Segoe UI', sans-serif;
  display: flex;
  flex-direction: column;
  gap: 1mm;
  overflow: hidden;
}

.label-names {
  font-size: 13pt;
  font-weight: 900;
  line-height: 1.15;
  color: #111;
  flex: 0 1 auto;
  max-height: 14mm;
  overflow: hidden;
  word-break: break-all;
}

.label-area {
  font-size: 8pt;
  font-weight: 800;
  color: #333;
}

.label-meal-line {
  font-size: 12pt;
  font-weight: 900;
  color: #0e5a44;
}

.label-rmk {
  font-size: 7pt;
  font-weight: 700;
  color: #b91c1c;
  line-height: 1.15;
  flex: 1 1 auto;
  max-height: 12mm;
  overflow: hidden;
  word-break: break-word;
}
</style>
