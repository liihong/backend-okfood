<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { Printer, RefreshCw, MapPin, Truck, FileDown } from 'lucide-vue-next'
import * as XLSX from 'xlsx'
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

/** 顺丰弹窗：期望送达 value-format 字符串，默认当日 12:00（与后端预览一致） */
function defaultSfExpectAt(ymd) {
  const d = (ymd || '').trim() || todayShanghaiStr()
  return `${d}T12:00:00`
}

/** 将接口返回的 expect_delivery_at 规范为 YYYY-MM-DDTHH:mm:ss，供 el-date-picker */
function expectAtToValueFormat(v, ymd) {
  if (v == null || v === '') return defaultSfExpectAt(ymd)
  const s = String(v)
  const m = s.match(/(\d{4}-\d{2}-\d{2})[Tt\s].*?(\d{1,2}):(\d{2}):(\d{2})/)
  if (m) {
    const hh = m[2].padStart(2, '0')
    return `${m[1]}T${hh}:${m[3]}:${m[4]}`
  }
  return defaultSfExpectAt(ymd)
}

/** 弹窗行：与会员地址 field 名对齐的 map/门牌 + 默认送达时间 */
function normalizeSfPreviewRows(rows, deliveryYmd) {
  const y = (deliveryYmd || '').trim() || todayShanghaiStr()
  return (Array.isArray(rows) ? rows : []).map((r) => {
    const map0 =
      r.map_location_text != null && String(r.map_location_text).length
        ? String(r.map_location_text)
        : String(r.recv_address ?? '')
    const door0 =
      r.door_detail != null && String(r.door_detail).length
        ? String(r.door_detail)
        : String(r.recv_building ?? '')
    return {
      ...r,
      map_location_text: map0,
      door_detail: door0,
      recv_address: map0,
      recv_building: door0,
      expect_delivery_at: expectAtToValueFormat(r.expect_delivery_at, y),
    }
  })
}

const sfExpectDefaultTime = new Date(2000, 0, 1, 12, 0, 0)

function onSfPushImmediatelyChange(row) {
  if (row && !row.push_immediately) {
    const ymd = (sfPreview.value.delivery_date || deliveryDateQuery.value || todayShanghaiStr()).trim()
    if (!row.expect_delivery_at) {
      row.expect_delivery_at = defaultSfExpectAt(ymd)
    }
  }
}

/** 与 GET /api/admin/delivery-sheet 响应字段对齐（含到家送达汇总） */
const emptySheet = () => ({
  delivery_date: '',
  groups: [],
  active_regions: [],
  home_pending_meal_total: 0,
  home_delivered_meal_total: 0,
  pickup_meal_total: 0,
  /** 与后端一致：false 表示周日/法定假等不生成订阅大表 */
  is_subscription_delivery_day: true,
})

const areaFilter = ref('')
/** 按手机号筛选大表（与 GET delivery-sheet ?phone= 一致；可后几位或完整号码） */
const phoneQuery = ref('')
/** 查询用的配送业务日（上海日历日 YYYY-MM-DD），可与「今天」不同 */
const deliveryDateQuery = ref(todayShanghaiStr())
/** 与后端 delivery_regions 启用列表同源（来自 delivery-sheet 响应） */
const activeRegions = ref([])
const sheetToday = ref(emptySheet())
const loading = ref(false)
/** 正在提交人工标记的 member_id，用于防重复点按 */
const markingMemberId = ref(null)
/** 批量标记送达进行中 */
const batchMarking = ref(false)
/** 配送大表 el-table 多选 */
const deliveryTableRef = ref(null)
const selectedDeliveryStops = ref([])

/** 顺丰同城：预览弹窗 */
const sfDialogOpen = ref(false)
const sfLoading = ref(false)
const sfPushSubmitting = ref(false)
const sfPreview = ref({ delivery_date: '', rows: [], sf_configured: false })
const sfSelectAll = ref(true)
/** 顺丰弹窗内：按收货人手机（表格「手机」列）再筛选，支持后几位或完整号 */
const sfModalPhoneFilter = ref('')

const sfModalFilteredRows = computed(() => {
  const rows = sfPreview.value.rows || []
  const q = (sfModalPhoneFilter.value || '').trim().replace(/\s/g, '')
  if (!q) return rows
  return rows.filter((r) => {
    const phone = String(r.recv_phone ?? '').replace(/\s/g, '')
    return phone.includes(q)
  })
})

const sfModalFilterActive = computed(() =>
  Boolean((sfModalPhoneFilter.value || '').trim().replace(/\s/g, ''))
)

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

/** 片区 Tab 副文案：到家展示待/已送达份数；自提单独说明 */
function groupTabMetaLine(group) {
  if (!group) return ''
  const meal = group.meal_total ?? 0
  const stops = group.stop_count ?? 0
  if (group.area === '门店自提') {
    const p = group.pending_meal_total ?? meal
    const d = group.delivered_meal_total ?? 0
    return `${meal} 份 · 待${p} · 已${d} · 自提`
  }
  const p = group.pending_meal_total ?? meal
  const d = group.delivered_meal_total ?? 0
  return `${meal} 份 · ${stops} 点 · 待${p} · 已${d}`
}

/** 联系人旁：到家为待/已送达；自提为待/已取 */
function deliveryMemberStatusLabel(group, m) {
  if (!group) return '—'
  if (group.area === '门店自提') {
    return m.is_delivered ? '已取' : '待自提'
  }
  return m.is_delivered ? '已送达' : '待送达'
}

function deliveryMemberStatusClass(group, m) {
  if (!group) return 'delivery-status-tag--pending'
  if (group.area === '门店自提') {
    return m.is_delivered ? 'delivery-status-tag--done' : 'delivery-status-tag--pickup'
  }
  return m.is_delivered ? 'delivery-status-tag--done' : 'delivery-status-tag--pending'
}

/** 配送点行：片区告警优先；到家再区分整点已送完 / 部分送达 */
function deliveryStopRowClassName({ row }) {
  const classes = []
  if (row.has_area_issue) classes.push('delivery-row--area-warn')
  const g = selectedGroup.value
  if (g?.area === '门店自提') return classes.join(' ')
  const pending = row.pending_meal_count
  const delivered = row.delivered_meal_count
  if (pending != null && delivered != null) {
    if (delivered > 0 && pending === 0) classes.push('delivery-row--done')
    else if (delivered > 0 && pending > 0) classes.push('delivery-row--partial')
  }
  return classes.join(' ')
}

async function fetchSheet() {
  if (!adminAccessToken.value) return
  loading.value = true
  const d0 = (deliveryDateQuery.value || '').trim() || todayShanghaiStr()
  try {
    const base = new URLSearchParams()
    const a = (areaFilter.value || '').trim()
    if (a) base.set('area', a)
    const ph = (phoneQuery.value || '').trim()
    if (ph) base.set('phone', ph)

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
      home_pending_meal_total: Number(data0?.home_pending_meal_total) || 0,
      home_delivered_meal_total: Number(data0?.home_delivered_meal_total) || 0,
      pickup_meal_total: Number(data0?.pickup_meal_total) || 0,
      is_subscription_delivery_day:
        data0?.is_subscription_delivery_day !== false,
    }
    syncDeliveryRegionTabs()
    clearDeliverySelection()
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

/** 与后端配送大表一致：address_line 为「片区 + 空格 + 详细」；导出 Excel 时配送地址列仅保留详细段（片区另列「地址片区」）。自提整行保留原样。 */
function addressLineForExcelExport(st) {
  if (st.groupArea === '门店自提') {
    return st.address_line != null ? String(st.address_line) : ''
  }
  const line = String(st.address_line ?? '').trim()
  const ar = String(st.area ?? '').trim()
  if (ar && line.startsWith(`${ar} `)) {
    return line.slice(ar.length + 1).trim()
  }
  if (ar && line.startsWith(ar)) {
    return line.slice(ar.length).trim()
  }
  return line
}

/**
 * 将当前大表导出为 xlsx：一行对应一名会员，地址为停靠点级别（同址多会员时地址重复）。
 * 数据与页面列表一致（同一配送日 + 当前片区/手机号筛选）；清空筛选即为当日全量。
 */
function exportSheetToExcel() {
  const d = String(sheetToday.value.delivery_date || deliveryDateQuery.value || todayShanghaiStr()).trim()
  const out = []
  for (const st of flatStops.value) {
    const isPickup = st.groupArea === '门店自提'
    for (const m of st.members || []) {
      const status = isPickup
        ? m.is_delivered
          ? '已取'
          : '待自提'
        : m.is_delivered
          ? '已送达'
          : '待送达'
      out.push({
        配送业务日: d,
        线路分组: st.groupArea ?? '',
        地址片区: st.area ?? '',
        配送地址: addressLineForExcelExport(st),
        会员ID: m.member_id,
        姓名: m.name != null ? String(m.name) : '',
        手机: m.phone != null ? String(m.phone) : '',
        当日期数: m.daily_meal_units ?? 0,
        备注: m.remarks != null && String(m.remarks).length ? String(m.remarks) : '',
        送达状态: status,
        片区待核实: m.area_issue || st.has_area_issue ? '是' : '否',
      })
    }
  }
  if (!out.length) {
    showToast('没有可导出的配送记录', 'error')
    return
  }
  const ws = XLSX.utils.json_to_sheet(out)
  ws['!cols'] = [
    { wch: 12 },
    { wch: 10 },
    { wch: 12 },
    { wch: 40 },
    { wch: 10 },
    { wch: 10 },
    { wch: 14 },
    { wch: 8 },
    { wch: 28 },
    { wch: 10 },
    { wch: 10 },
  ]
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '配送清单')
  XLSX.writeFile(wb, `配送清单_${d}.xlsx`)
  showToast(`已导出 ${out.length} 行`, 'success')
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

function markBusy(memberId) {
  return batchMarking.value || (markingMemberId.value != null && Number(markingMemberId.value) === Number(memberId))
}

/** el-table row-key：同一片区内按地址区分（与后端停靠点聚合一致） */
function deliveryStopRowKey(row) {
  const g = activeRegionTab.value || ''
  return `${g}\u0001${row.address_line || ''}`
}

function selectableDeliveryStop(row) {
  const members = row.members || []
  return members.some((m) => !m.is_delivered)
}

function onDeliverySelectionChange(rows) {
  selectedDeliveryStops.value = rows || []
}

const batchPendingMemberCount = computed(() => {
  let n = 0
  for (const st of selectedDeliveryStops.value) {
    for (const m of st.members || []) {
      if (!m.is_delivered) n += 1
    }
  }
  return n
})

function clearDeliverySelection() {
  deliveryTableRef.value?.clearSelection?.()
  selectedDeliveryStops.value = []
}

watch(activeRegionTab, () => {
  clearDeliverySelection()
})

async function markSelectedStopsDelivered() {
  if (batchMarking.value || !selectedGroup.value) return
  const kind = selectedGroup.value.area === '门店自提' ? 'pickup' : 'home'
  const pendingIds = []
  for (const st of selectedDeliveryStops.value) {
    for (const m of st.members || []) {
      if (!m.is_delivered) pendingIds.push(m.member_id)
    }
  }
  if (!pendingIds.length) {
    showToast('所选行中没有待标记的会员', 'info')
    return
  }
  batchMarking.value = true
  const d0 = String(sheetToday.value.delivery_date || deliveryDateQuery.value || todayShanghaiStr()).trim()
  try {
    for (const memberId of pendingIds) {
      await apiJson(
        '/api/admin/delivery-mark',
        {
          method: 'POST',
          body: JSON.stringify({ member_id: Number(memberId), delivery_date: d0, kind }),
        },
        { auth: true }
      )
    }
    showToast(`已标记 ${pendingIds.length} 位会员`, 'success')
    clearDeliverySelection()
    await fetchSheet()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '批量标记失败', 'error')
  } finally {
    batchMarking.value = false
  }
}

function applySfSelectAll(val) {
  const rows = sfModalFilteredRows.value
  for (const r of rows) {
    if (!r.already_pushed) {
      r.selected = val
    }
  }
}

async function openSfDialog() {
  if (!adminAccessToken.value) return
  sfModalPhoneFilter.value = ''
  sfDialogOpen.value = true
  sfLoading.value = true
  const d0 = (deliveryDateQuery.value || '').trim() || todayShanghaiStr()
  const base = new URLSearchParams()
  base.set('delivery_date', d0)
  const a = (areaFilter.value || '').trim()
  if (a) base.set('area', a)
  const ph = (phoneQuery.value || '').trim()
  if (ph) base.set('phone', ph)
  try {
    const data = await apiJson(`/api/admin/delivery-sf/preview?${base.toString()}`, {}, { auth: true })
    const d1 = data?.delivery_date || d0
    sfPreview.value = {
      delivery_date: d1,
      rows: normalizeSfPreviewRows(data?.rows, d1),
      sf_configured: Boolean(data?.sf_configured),
    }
    sfSelectAll.value = true
    applySfSelectAll(true)
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载顺丰预览失败', 'error')
    sfPreview.value = { delivery_date: d0, rows: [], sf_configured: false }
  } finally {
    sfLoading.value = false
  }
}

async function submitSfPush() {
  if (sfPushSubmitting.value) return
  const d0 = (sfPreview.value.delivery_date || deliveryDateQuery.value || todayShanghaiStr()).trim()
  const rows = (sfPreview.value.rows || []).map((r) => ({ ...r }))
  if (!rows.length) {
    showToast('没有可推单的停靠点', 'error')
    return
  }
  sfPushSubmitting.value = true
  try {
    const payload = {
      delivery_date: d0,
      rows: rows.map((r) => {
        const mapT = String(r.map_location_text ?? r.recv_address ?? '').trim()
        const doorD = String(r.door_detail ?? r.recv_building ?? '').trim()
        let expectAt = r.expect_delivery_at
        if (!r.push_immediately) {
          expectAt = expectAt || defaultSfExpectAt(d0)
        } else {
          expectAt = null
        }
        return {
          ...r,
          map_location_text: mapT,
          door_detail: doorD,
          recv_address: mapT,
          recv_building: doorD,
          goods_value_yuan: r.is_insured ? r.goods_value_yuan : null,
          expect_delivery_at: expectAt,
        }
      }),
    }
    const data = await apiJson(
      '/api/admin/delivery-sf/push',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      { auth: true }
    )
    const results = Array.isArray(data?.results) ? data.results : []
    const fail = results.filter((x) => x && !x.ok)
    if (fail.length) {
      const msg = fail.map((f) => `${f.stop_id?.slice(0, 8)}: ${f.message || ''}`).join('；')
      showToast(`部分失败：${msg}`, 'error')
    } else {
      showToast('已全部提交', 'success')
    }
    sfDialogOpen.value = false
  } catch (e) {
    showToast(e instanceof Error ? e.message : '推单失败', 'error')
  } finally {
    sfPushSubmitting.value = false
  }
}

async function markDelivery(memberId, kind) {
  if (batchMarking.value || markingMemberId.value != null) return
  const d0 = String(sheetToday.value.delivery_date || deliveryDateQuery.value || todayShanghaiStr()).trim()
  markingMemberId.value = memberId
  try {
    await apiJson(
      '/api/admin/delivery-mark',
      {
        method: 'POST',
        body: JSON.stringify({ member_id: Number(memberId), delivery_date: d0, kind }),
      },
      { auth: true }
    )
    showToast('已标记', 'success')
    await fetchSheet()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '操作失败', 'error')
  } finally {
    markingMemberId.value = null
  }
}
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
          <label class="delivery-field delivery-field--phone">
            <span>手机号</span>
            <div class="delivery-phone-row">
              <el-input
                v-model="phoneQuery"
                placeholder="后四位或完整号码"
                clearable
                :disabled="loading"
                class="delivery-el-phone"
                @clear="fetchSheet"
                @keyup.enter="fetchSheet"
              />
              <button
                type="button"
                class="btn-ghost delivery-phone-search"
                :disabled="loading"
                @click="fetchSheet"
              >
                查询
              </button>
            </div>
          </label>
        </div>
        <div class="delivery-toolbar__actions">
          <p class="delivery-meta">
            到家：待送达 <strong>{{ sheetToday.home_pending_meal_total }}</strong> 份、已送达
            <strong>{{ sheetToday.home_delivered_meal_total }}</strong> 份
            <template v-if="sheetToday.pickup_meal_total > 0">
              · 门店自提 <strong>{{ sheetToday.pickup_meal_total }}</strong> 份
            </template>
            <br />
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
            class="delivery-excel-btn"
            :disabled="loading || !flatStops.length"
            title="与下方列表数据一致；清空片区/手机号可导出该业务日全量"
            @click="exportSheetToExcel"
          >
            <FileDown :size="18" />
            导出 Excel
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
          <button
            type="button"
            class="btn-ghost delivery-sf-btn"
            :disabled="loading"
            :title="!sfPreview.sf_configured ? '请在后端 .env 配置顺丰开发者参数' : ''"
            @click="openSfDialog"
          >
            <Truck :size="18" />
            顺丰推单
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
            <span class="delivery-region-tab__meta">{{ groupTabMetaLine(group) }}</span>
          </button>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="sfDialogOpen"
      title="顺丰同城创单：核对后提交"
      width="min(1200px, 96vw)"
      class="sf-dialog"
      destroy-on-close
      :close-on-press-escape="true"
    >
      <p v-if="!sfLoading && !sfPreview.sf_configured" class="sf-warn">
        未配置顺丰账号：请在 API 的 .env 中设置 <code>SF_OPEN_DEV_ID</code>、<code>SF_OPEN_SHOP_ID</code>、<code>SF_OPEN_SECRET</code> 以及
        <code>SF_PICKUP_PHONE</code>、<code>SF_PICKUP_ADDRESS</code>（取货电话与取货地址）。
      </p>
      <p v-if="sfLoading" class="members-loading">加载推单清单…</p>
      <template v-else>
        <div class="sf-bar">
          <div class="sf-bar__left">
            <label class="sf-check-all"
              ><input v-model="sfSelectAll" type="checkbox" @change="applySfSelectAll(sfSelectAll)" />
              全选</label
            >
            <span class="sf-hint"
              >业务日 <strong>{{ sfPreview.delivery_date || deliveryDateQuery }}</strong> ·
              共 {{ sfModalFilteredRows.length }} 个停靠点<span v-if="sfModalFilterActive"
                >（全量 {{ (sfPreview.rows || []).length }}）</span
              >；取消勾选则该行不推。</span
            >
          </div>
          <div class="sf-bar__right">
            <span class="sf-bar__filter-label">收货手机筛选</span>
            <el-input
              v-model="sfModalPhoneFilter"
              clearable
              placeholder="后几位或完整号"
              maxlength="20"
              size="small"
              class="sf-bar__filter-input"
              @keydown.stop
            />
          </div>
        </div>
        <div class="sf-table-wrap">
          <el-table
            v-if="(sfPreview.rows || []).length && sfModalFilteredRows.length"
            :data="sfModalFilteredRows"
            border
            size="small"
            stripe
            class="sf-table"
            max-height="420"
          >
            <el-table-column width="48" label="选" align="center" fixed>
              <template #default="{ row }">
                <el-checkbox v-model="row.selected" :disabled="row.already_pushed" />
              </template>
            </el-table-column>
            <el-table-column prop="group_area" label="片区" min-width="88" show-overflow-tooltip />
            <el-table-column prop="pickup_phone" label="取货电话" min-width="120" show-overflow-tooltip />
            <el-table-column min-width="120" label="收货地址" show-overflow-tooltip>
              <template #header>
                <span title="与会员地址 map_location_text 一致">收货地址</span>
              </template>
              <template #default="{ row }">
                <el-input v-model="row.map_location_text" size="small" />
              </template>
            </el-table-column>
            <el-table-column min-width="100" label="门牌" show-overflow-tooltip>
              <template #header>
                <span title="与会员地址 door_detail 一致">门牌</span>
              </template>
              <template #default="{ row }">
                <el-input v-model="row.door_detail" size="small" />
              </template>
            </el-table-column>
            <el-table-column min-width="80" label="姓名" show-overflow-tooltip>
              <template #default="{ row }">
                <el-input v-model="row.recv_name" size="small" />
              </template>
            </el-table-column>
            <el-table-column min-width="120" label="手机" show-overflow-tooltip>
              <template #default="{ row }">
                <el-input v-model="row.recv_phone" size="small" />
              </template>
            </el-table-column>
            <el-table-column min-width="100" label="品类" show-overflow-tooltip>
              <template #default="{ row }">
                <el-input v-model="row.product_category" size="small" />
              </template>
            </el-table-column>
            <el-table-column width="88" label="重(kg)">
              <template #default="{ row }">
                <el-input-number v-model="row.weight_kg" :min="0.1" :max="200" :step="0.1" size="small" controls-position="right" class="sf-num" />
              </template>
            </el-table-column>
            <el-table-column width="100" label="立即推单" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.push_immediately" @change="onSfPushImmediatelyChange(row)" />
              </template>
            </el-table-column>
            <el-table-column min-width="160" label="期望送达">
              <template #default="{ row }">
                <el-date-picker
                  v-model="row.expect_delivery_at"
                  type="datetime"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  :default-time="sfExpectDefaultTime"
                  placeholder="默认 12:00，可改"
                  size="small"
                  class="sf-dt"
                  :disabled="row.push_immediately"
                />
              </template>
            </el-table-column>
            <el-table-column min-width="120" label="备注" show-overflow-tooltip>
              <template #default="{ row }">
                <el-input v-model="row.remark" size="small" />
              </template>
            </el-table-column>
            <el-table-column width="88" label="专人" align="center">
              <template #default="{ row }">
                <el-checkbox v-model="row.is_direct" />
              </template>
            </el-table-column>
            <el-table-column min-width="80" label="车型" show-overflow-tooltip>
              <template #default="{ row }">
                <el-input v-model="row.vehicle_type" size="small" />
              </template>
            </el-table-column>
            <el-table-column width="72" label="保价" align="center">
              <template #default="{ row }">
                <el-checkbox v-model="row.is_insured" />
              </template>
            </el-table-column>
            <el-table-column min-width="88" label="货值(元)">
              <template #default="{ row }">
                <el-input-number
                  v-model="row.goods_value_yuan"
                  :min="0"
                  :step="0.01"
                  :disabled="!row.is_insured"
                  size="small"
                  class="sf-num"
                  controls-position="right"
                />
              </template>
            </el-table-column>
            <el-table-column width="72" label="已推" align="center">
              <template #default="{ row }">
                <span v-if="row.already_pushed" class="sf-bad">是</span>
                <span v-else>否</span>
              </template>
            </el-table-column>
          </el-table>
          <p v-else-if="(sfPreview.rows || []).length" class="sf-empty">
            当前「收货手机筛选」下没有匹配的停靠点，请清空或修改筛选项。
          </p>
          <p v-else class="sf-empty">当前筛选下没有可推单的停靠点（无待送订阅/单点）。</p>
        </div>
      </template>
      <template #footer>
        <el-button :disabled="sfLoading" @click="sfDialogOpen = false">取消</el-button>
        <el-button
          type="primary"
          :loading="sfPushSubmitting"
          :disabled="sfLoading || !(sfPreview.rows || []).length"
          @click="submitSfPush"
        >
          确认推送到顺丰
        </el-button>
      </template>
    </el-dialog>

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
          <p v-if="!sheetToday.groups?.length" class="members-loading">
            <template v-if="sheetToday.is_subscription_delivery_day === false">
              该日非订阅配送业务日：周日、国家法定节假日及国务院调休放假日不生成大表，份数不计入该日。请选择其它业务日，或在「营业概览」核对备餐人数是否为 0。
            </template>
            <template v-else-if="(phoneQuery || '').trim()">
              该业务日无与「{{ (phoneQuery || '').trim() }}」匹配的配送记录（或该会员已请假/未在配送名单中）。
            </template>
            <template v-else>
              当日暂无符合大表条件的会员（请假、未激活、余额不足、起送日晚于该日、片区筛选无匹配等）。单点餐在「顺丰同城」预览里与订阅合并，本页仅含订阅与自提。
            </template>
          </p>
          <div v-else class="delivery-region-tabs">
            <div v-if="selectedGroup" role="tabpanel" :aria-label="selectedGroup.area" class="delivery-tabpanel">
              <div class="group-card">
                <div class="group-header" :class="{ 'group-header--area-warn': selectedGroup.has_area_issue }">
                  <h4>
                    <MapPin :size="18" class="inline-icon" />
                    {{ selectedGroup.area }}
                    <span v-if="selectedGroup.has_area_issue" class="group-area-badge">区域待维护</span>
                  </h4>
                  <span class="badge">{{ groupTabMetaLine(selectedGroup) }}</span>
                </div>
                <div class="delivery-batch-bar">
                  <span class="delivery-batch-bar__hint">
                    勾选左侧行可批量操作；已选 <strong>{{ selectedDeliveryStops.length }}</strong> 个配送点，待标记
                    <strong>{{ batchPendingMemberCount }}</strong> 位会员
                  </span>
                  <div class="delivery-batch-bar__actions">
                    <button
                      type="button"
                      class="btn-primary delivery-batch-bar__btn"
                      :disabled="
                        loading ||
                        batchMarking ||
                        !batchPendingMemberCount ||
                        !selectedDeliveryStops.length
                      "
                      @click="markSelectedStopsDelivered"
                    >
                      {{ selectedGroup.area === '门店自提' ? '批量自提完成' : '批量标记送达' }}
                    </button>
                    <button
                      type="button"
                      class="btn-ghost delivery-batch-bar__btn"
                      :disabled="!selectedDeliveryStops.length || batchMarking"
                      @click="clearDeliverySelection"
                    >
                      清空选择
                    </button>
                  </div>
                </div>
                <div class="group-card__table-scroll">
                <AdminTable
                  ref="deliveryTableRef"
                  variant="delivery"
                  size="small"
                  :data="selectedGroup.stops"
                  :row-key="deliveryStopRowKey"
                  :row-class-name="deliveryStopRowClassName"
                  :stripe="false"
                  empty-text="暂无配送点"
                  @selection-change="onDeliverySelectionChange"
                >
                  <el-table-column
                    type="selection"
                    width="44"
                    align="center"
                    fixed
                    class-name="col-sel"
                    :selectable="selectableDeliveryStop"
                  />
                  <el-table-column label="序号" width="64" min-width="56" class-name="col-idx">
                    <template #default="{ $index }">
                      <span class="t-idx">{{ $index + 1 }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="餐数" width="108" min-width="96" class-name="col-meals">
                    <template #default="{ row: st }">
                      <div class="meal-cell">
                        <span class="meal-pill">{{ st.meal_count }}</span>
                        <span
                          v-if="st.pending_meal_count != null"
                          class="meal-pill-sub"
                        >
                          待{{ st.pending_meal_count }} · 已{{ st.delivered_meal_count }}
                        </span>
                      </div>
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
                        <span class="delivery-status-tag" :class="deliveryMemberStatusClass(selectedGroup, m)">
                          {{ deliveryMemberStatusLabel(selectedGroup, m) }}
                        </span>
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
                  <el-table-column label="操作" width="128" min-width="108" class-name="col-actions" fixed="right">
                    <template #default="{ row: st }">
                      <div
                        v-for="(m, mi) in st.members"
                        :key="'op-' + m.member_id + '-' + mi"
                        class="delivery-action-line"
                      >
                        <button
                          v-if="!m.is_delivered"
                          type="button"
                          class="btn-delivery-mark"
                          :disabled="markBusy(m.member_id) || loading || batchMarking"
                          @click="markDelivery(m.member_id, selectedGroup?.area === '门店自提' ? 'pickup' : 'home')"
                        >
                          {{
                            markBusy(m.member_id)
                              ? '提交中'
                              : selectedGroup?.area === '门店自提'
                                ? '自提完成'
                                : '标记送达'
                          }}
                        </button>
                        <span v-else class="delivery-action-done">已标记</span>
                      </div>
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
.delivery-sf-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.sf-warn {
  margin: 0 0 0.75rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  color: #b45309;
  background: #fffbeb;
  border-radius: 0.5rem;
}
.sf-warn code {
  font-size: 0.75rem;
}
.sf-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem 1rem;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
}
.sf-bar__left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1rem;
  min-width: 0;
}
.sf-bar__right {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex: 0 0 auto;
}
.sf-bar__filter-label {
  white-space: nowrap;
  color: #64748b;
  font-size: 0.82rem;
}
.sf-bar__filter-input {
  width: 11rem !important;
  max-width: 40vw;
}
.sf-check-all {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  cursor: pointer;
  user-select: none;
}
.sf-hint {
  color: #64748b;
}
.sf-table-wrap {
  width: 100%;
  overflow-x: auto;
}
.sf-table {
  min-width: 900px;
}
.sf-num {
  width: 100% !important;
}
:deep(.sf-dt) {
  width: 100%;
}
.sf-bad {
  color: #dc2626;
  font-weight: 700;
}
.sf-empty {
  margin: 0;
  padding: 1rem;
  color: #64748b;
  font-size: 0.9rem;
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
.delivery-field--phone {
  min-width: 0;
}
.delivery-phone-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
.delivery-field :deep(.delivery-el-phone) {
  width: 11rem;
  max-width: 100%;
}
.delivery-field :deep(.delivery-el-phone .el-input__wrapper) {
  border-radius: 0.75rem;
}
.delivery-phone-search {
  padding: 0.45rem 0.85rem;
  border-radius: 0.75rem;
  font-weight: 800;
  font-size: 0.75rem;
  white-space: nowrap;
}
.delivery-icon-btn,
.delivery-excel-btn,
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
.delivery-excel-btn {
  background: #e8f5e9;
  color: #1b5e20;
}
.delivery-excel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
  margin-bottom: 0.15rem;
  line-height: 1.25;
}
.contact-line:last-child {
  margin-bottom: 0;
}
.meal-pill {
  display: inline-block;
  min-width: 1.85rem;
  text-align: center;
  font-weight: 900;
  font-size: 1rem;
  line-height: 1.2;
  color: #0e5a44;
  background: #d1fae5;
  padding: 0.12rem 0.42rem;
  border-radius: 0.4rem;
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

.delivery-status-tag {
  display: inline-block;
  margin-right: 0.3rem;
  font-size: 9px;
  font-weight: 900;
  padding: 1px 5px;
  border-radius: 4px;
  vertical-align: middle;
}
.delivery-status-tag--done {
  background: #d1fae5;
  color: #065f46;
}
.delivery-status-tag--pending {
  background: #fef3c7;
  color: #92400e;
}
.delivery-status-tag--pickup {
  background: #e0e7ff;
  color: #3730a3;
}

.delivery-batch-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem 1rem;
  padding: 0.45rem 1rem;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 0.75rem;
  color: #64748b;
}
.delivery-batch-bar__hint strong {
  color: #0f172a;
}
.delivery-batch-bar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
.delivery-batch-bar__btn {
  padding: 0.35rem 0.85rem;
  font-size: 0.75rem;
  font-weight: 800;
  border-radius: 0.5rem;
  white-space: nowrap;
}

.meal-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.08rem;
}
.meal-pill-sub {
  font-size: 0.65rem;
  font-weight: 700;
  color: #64748b;
  white-space: nowrap;
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

.delivery-action-line {
  display: flex;
  align-items: center;
  min-height: 1.6rem;
  margin-bottom: 0.25rem;
}
.delivery-action-line:last-child {
  margin-bottom: 0;
}
.btn-delivery-mark {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 0.45rem;
  font-size: 0.7rem;
  font-weight: 800;
  cursor: pointer;
  border: 1px solid #0e5a44;
  background: #ecfdf3;
  color: #0e5a44;
}
.btn-delivery-mark:hover:not(:disabled) {
  background: #0e5a44;
  color: #fff;
}
.btn-delivery-mark:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.delivery-action-done {
  font-size: 0.7rem;
  font-weight: 800;
  color: #0e5a44;
}
</style>
