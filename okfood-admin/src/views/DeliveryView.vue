<script setup>
defineOptions({ name: 'DeliveryView' })
import { ref, computed, watch, onMounted } from 'vue'
import { RefreshCw, MapPin, Truck, Zap, FileDown, Search, Loader2, Printer, Gift } from 'lucide-vue-next'
import * as XLSX from 'xlsx'
import { apiJson, adminAccessToken, adminStoreBranding, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import { toastSfPushBatchOutcome, toastSfPushError } from '../utils/sfPushMessages.js'
import {
  SF_PUSH_MODE_SHEET,
  SF_PUSH_MODE_INSTANT,
  SHEET_VIEW_LUNCH,
  SHEET_VIEW_DINNER,
  SHEET_VIEW_LUNCH_DINNER,
  buildSfPushPayload,
  deliveryMarkMealPeriod,
  getDeliverySheetApiPath,
  getSfPushApiPath,
  getSfPushPreviewApiPath,
  isSfPushConfigured,
  sheetViewSupportsSfPush,
  validateSfSheetPushRows,
} from '../composables/delivery/useDeliverySfPush.js'
import { useAnimatedInteger } from '../composables/useAnimatedInteger.js'
import { useStorePrint } from '../composables/useStorePrint.js'
import { buildDeliveryLabelItems, missingRegionCodesForStops } from '../utils/print/deliveryLabelAdapter.js'
import GiftCouponTodayDialog from './delivery/GiftCouponTodayDialog.vue'
import OkfoodAdminDialogShell from '../components/OkfoodAdminDialogShell.vue'

const { submitPrintJob, printing: printLoading, resolveScene } = useStorePrint()

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

/**
 * 将上海日历日 YYYY-MM-DD 前移或后移若干整日（午间 +08:00 锚点，减少日界线歧义）
 * @param {string} ymdStr
 * @param {number} deltaDays 负数为前一天
 */
function shiftShanghaiCalendarYmd(ymdStr, deltaDays) {
  const raw = String(ymdStr || '').trim().match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!raw) return todayShanghaiStr()
  const base = new Date(`${raw[1]}-${raw[2]}-${raw[3]}T12:00:00+08:00`)
  const ms = base.getTime() + Number(deltaDays) * 86400000
  return ymdInTimeZone(new Date(ms), 'Asia/Shanghai')
}

/** 业务日已过时，期望送达默认用「今日」起算，避免仍落在历史日期 */
function effectiveSfExpectDefaultYmd(deliveryYmd) {
  const yRaw = (deliveryYmd || '').trim() || todayShanghaiStr()
  return yRaw < todayShanghaiStr() ? todayShanghaiStr() : yRaw
}

/**
 * 顺丰弹窗：期望送达 value-format 字符串。
 * 午餐默认当日 12:00（与后端预览一致）；晚餐仅前端改成 18:00，不改后端。
 */
function defaultSfExpectAt(ymd) {
  const d = (ymd || '').trim() || todayShanghaiStr()
  const hour = sheetView.value === SHEET_VIEW_DINNER ? '18' : '12'
  return `${d}T${hour}:00:00`
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
  const yRaw = (deliveryYmd || '').trim() || todayShanghaiStr()
  const y = effectiveSfExpectDefaultYmd(yRaw)
  const today = todayShanghaiStr()
  return (Array.isArray(rows) ? rows : []).map((r) => {
    const map0 =
      r.map_location_text != null && String(r.map_location_text).length
        ? String(r.map_location_text)
        : String(r.recv_address ?? '')
    const door0 =
      r.door_detail != null && String(r.door_detail).length
        ? String(r.door_detail)
        : String(r.recv_building ?? '')
    let exp = expectAtToValueFormat(r.expect_delivery_at, y)
    if (yRaw < today) {
      const expYmd = String(exp || '').split('T')[0]
      if (!expYmd || expYmd < today) exp = defaultSfExpectAt(y)
    }
    // 后端午餐/晚餐预览都固定带当天 12:00；晚餐推单在这里改成 18:00
    if (sheetView.value === SHEET_VIEW_DINNER) {
      const noon = String(exp || '').match(/^(\d{4}-\d{2}-\d{2})T12:00:00$/)
      if (noon) exp = `${noon[1]}T18:00:00`
    }
    return {
      ...r,
      map_location_text: map0,
      door_detail: door0,
      recv_address: map0,
      recv_building: door0,
      expect_delivery_at: exp,
    }
  })
}

const sfExpectDefaultTime = computed(
  () => new Date(2000, 0, 1, sheetView.value === SHEET_VIEW_DINNER ? 18 : 12, 0, 0),
)

function onSfPushImmediatelyChange(row) {
  if (row && !row.push_immediately) {
    const ymd = effectiveSfExpectDefaultYmd(sfPreview.value.delivery_date || deliveryDateQuery.value)
    if (!row.expect_delivery_at) {
      row.expect_delivery_at = defaultSfExpectAt(ymd)
    }
  }
}

/** 解析顺丰弹窗 expect_delivery_at（墙钟 +08:00）与当前时刻比较 */
function parseSfExpectAtShanghai(s) {
  const m = String(s || '').match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})$/)
  if (!m) return null
  return new Date(`${m[1]}T${m[2]}:${m[3]}:${m[4]}+08:00`)
}

/** 业务日早于今日时，禁止期望送达选上日历今日之前的日期 */
function sfExpectDeliveryDisabledDate(time) {
  const d = String(sfPreview.value.delivery_date || '').trim()
  if (!d || d >= todayShanghaiStr()) return false
  const ymd = ymdInTimeZone(time, 'Asia/Shanghai')
  return ymd < todayShanghaiStr()
}

/** 与 GET /api/admin/delivery-sheet 响应字段对齐（含到家送达汇总） */
const emptySheet = () => ({
  delivery_date: '',
  groups: [],
  active_regions: [],
  region_codes: {},
  home_pending_meal_total: 0,
  home_delivered_meal_total: 0,
  pickup_meal_total: 0,
  /** 与后端一致：false 表示周日/法定假等不生成订阅大表 */
  is_subscription_delivery_day: true,
  total_members: 0,
  active_weekly_members: 0,
  expired_weekly_members: 0,
  active_monthly_members: 0,
  expired_monthly_members: 0,
})

/** 大表视图 Tab：午餐 / 晚餐 / 午晚餐双餐段运维 */
const sheetView = ref(SHEET_VIEW_LUNCH)
const sheetViewLabel = computed(() => {
  if (sheetView.value === SHEET_VIEW_DINNER) return '晚餐'
  if (sheetView.value === SHEET_VIEW_LUNCH_DINNER) return '午晚餐'
  return '午餐'
})
const sfPushEnabledForView = computed(() => sheetViewSupportsSfPush(sheetView.value))

/** 按手机号筛选大表（与 GET delivery-sheet ?phone= 一致；可后几位或完整号码） */
const phoneQuery = ref('')
const reinstateBusy = ref(false)
/** 查询用的配送业务日（日历日 YYYY-MM-DD），可与「今天」不同 */
const deliveryDateQuery = ref(todayShanghaiStr())

const sheetToday = ref(emptySheet())
const loading = ref(false)
/** 正在提交人工标记的 member_id，用于防重复点按 */
const markingMemberId = ref(null)
/** 导出 Excel 时并行拉取午餐、晚餐两张大表，避免连点重复请求 */
const exportBusy = ref(false)
/** 批量标记送达进行中 */
const batchMarking = ref(false)
/** 配送大表 el-table 多选 */
const deliveryTableRef = ref(null)
const selectedDeliveryStops = ref([])
/** 今日礼品券打印/核销弹窗（独立模块，不改配送名单） */
const giftCouponDialogVisible = ref(false)

/** 顺丰同城：预览弹窗 */
const sfDialogOpen = ref(false)
const sfPushMode = ref(SF_PUSH_MODE_SHEET)
const sfLoading = ref(false)
const sfPushSubmitting = ref(false)
const sfPreview = ref({ delivery_date: '', rows: [], sf_configured: false, instant_sf_configured: false })
const sfPushHelpers = {
  defaultSfExpectAt,
  effectiveSfExpectDefaultYmd,
  parseSfExpectAtShanghai,
}
const sfPushModeIsInstant = computed(() => sfPushMode.value === SF_PUSH_MODE_INSTANT)
const sfDialogConfigured = computed(() => isSfPushConfigured(sfPreview.value, sfPushMode.value))
/** 顺丰弹窗当前业务日是否早于今日（历史日查询） */
const sfBizDayPast = computed(() => {
  const d = String(sfPreview.value.delivery_date || '').trim()
  return Boolean(d && d < todayShanghaiStr())
})
const sfSelectAll = ref(true)
/** 勾选后预览不按片区过滤（当日全部到家停靠点）；不勾选时用当前 Tab 对应片区（自提 Tab 不传 area） */
const sfPreviewAllRegions = ref(false)
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

/** 顺丰预览请求：未勾选「全部片区」时用当前 Tab（自提 Tab 不传 area，与原先全量到家一致） */
function sfPreviewQueryArea() {
  if (sfPreviewAllRegions.value) return ''
  const tab = (activeRegionTab.value || '').trim()
  if (tab === '门店自提') return ''
  return tab
}

const sfPreviewScopeHint = computed(() => {
  if (sfPreviewAllRegions.value) return '全部片区'
  const a = sfPreviewQueryArea()
  return a ? `片区「${a}」` : '全部片区'
})

/** 核对弹窗标题：及时单与同城预约是两个入口，不在弹窗里再切换 */
const sfDialogTitle = computed(() => (sfPushModeIsInstant.value ? '推送及时单' : '顺丰同城创单'))
const sfDialogSubtitle = computed(() =>
  sfPushModeIsInstant.value
    ? '将全部按立即推单创单，使用门店「零售推顺丰店铺ID」。适合当日部分停靠点补推，创单失败或已取消的记录可覆盖重推。'
    : '先核对停靠点，再推到顺丰。取消勾选则该行不推。',
)
/** 本次会提交的停靠点：已推过的行勾选框是禁用的 */
const sfPickedCount = computed(
  () => (sfPreview.value.rows || []).filter((row) => row.selected && !row.already_pushed).length,
)
const sfPickupPhoneLabel = computed(() => {
  const phones = [
    ...new Set(
      (sfPreview.value.rows || [])
        .map((row) => String(row.pickup_phone || '').trim())
        .filter(Boolean),
    ),
  ]
  if (!phones.length) return '—'
  if (phones.length === 1) return phones[0]
  return `${phones.length} 个号码`
})

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

/** 到家配送点数量（排除「门店自提」分组，自提不是配送停靠点） */
const homeDeliveryStopCount = computed(() => {
  let n = 0
  for (const g of sheetToday.value.groups || []) {
    if (g.area === '门店自提') continue
    n += (g.stops || []).length
  }
  return n
})

/** 到家合计份数（待送达 + 已送达），与接口根字段一致 */
const sheetHomeMealTotal = computed(
  () =>
    (Number(sheetToday.value.home_pending_meal_total) || 0) +
    (Number(sheetToday.value.home_delivered_meal_total) || 0),
)

const displayHomeMealTotal = useAnimatedInteger(() => sheetHomeMealTotal.value, { duration: 820 })
const displayPickupMealTotal = useAnimatedInteger(
  () => Number(sheetToday.value.pickup_meal_total) || 0,
  { duration: 820 },
)
const displayStopCount = useAnimatedInteger(() => homeDeliveryStopCount.value, { duration: 820 })

/** 当前所选业务日是否为上海「今天」（用于「今日实时」徽标） */
const deliveryQueryIsTodayShanghai = computed(
  () => String(deliveryDateQuery.value).trim() === todayShanghaiStr(),
)

/** 片区 Tab 副文案（与新版控制台 Tab 视觉一致：紧凑一行） */
function groupTabMetaLine(group) {
  if (!group) return ''
  const meal = group.meal_total ?? 0
  const stops = group.stop_count ?? 0
  if (group.area === '门店自提') {
    return `${meal}份 · ${stops}点 · 自提`
  }
  const p = group.pending_meal_total ?? meal
  return `${meal}份 · ${stops}点 · 待${p}`
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
  if (row.sf_push_failed || (row.members || []).some((m) => m.missing_coords)) {
    classes.push('delivery-row--sf-fail')
  }
  const g = selectedGroup.value
  if (selectedDeliveryStops.value.some((stop) => deliveryStopRowKey(stop) === deliveryStopRowKey(row))) {
    classes.push('delivery-row--picked')
  }
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
    const ph = (phoneQuery.value || '').trim()
    if (ph) base.set('phone', ph)

    const q0 = new URLSearchParams(base)
    q0.set('delivery_date', d0)
    q0.set('include_member_stats', 'false')

    const data0 = await apiJson(`${getDeliverySheetApiPath(sheetView.value)}?${q0.toString()}`, {}, { auth: true })

    const regions0 = Array.isArray(data0?.active_regions) ? data0.active_regions : []

    const resolvedDate = data0?.delivery_date || d0
    if (data0?.delivery_date) deliveryDateQuery.value = data0.delivery_date
    sheetToday.value = {
      delivery_date: resolvedDate,
      groups: Array.isArray(data0?.groups) ? data0.groups : [],
      active_regions: regions0,
      region_codes:
        data0?.region_codes && typeof data0.region_codes === 'object' ? data0.region_codes : {},
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
    showToast(e instanceof Error ? e.message : '加载配送表失败', 'error')
  } finally {
    loading.value = false
  }
}

/** 顶栏：快捷增减配送业务日并重新拉取大表 */
function shiftDeliveryBizDayBy(delta) {
  const cur =
    deliveryDateQuery.value != null && String(deliveryDateQuery.value).trim() !== ''
      ? String(deliveryDateQuery.value).trim()
      : todayShanghaiStr()
  deliveryDateQuery.value = shiftShanghaiCalendarYmd(cur, delta)
  void fetchSheet()
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

/** 晚餐份数单元格：当日不在晚餐大表为「无」，在表上为「X份」。 */
function formatDinnerPortionsCell(units) {
  const n = Number(units)
  if (!Number.isFinite(n) || n <= 0) return '无'
  return `${Math.trunc(n)}份`
}

/**
 * 拉取某一餐段当日大表。手机号与查询框一致：空则该餐全量。
 * @param {'lunch' | 'dinner'} view
 * @param {string} deliveryDate
 * @param {string} phone
 */
async function fetchDeliverySheetForExport(view, deliveryDate, phone) {
  const q = new URLSearchParams()
  q.set('delivery_date', deliveryDate)
  q.set('include_member_stats', 'false')
  const ph = String(phone || '').trim()
  if (ph) q.set('phone', ph)
  return apiJson(`${getDeliverySheetApiPath(view)}?${q.toString()}`, {}, { auth: true })
}

/**
 * 把大表拆成会员行，保留片区顺序。同一会员只保留第一次出现。
 * @param {object | null | undefined} sheet
 */
function sheetExportEntries(sheet) {
  const entries = []
  const seen = new Set()
  for (const st of flatStopsForSheet(sheet || {})) {
    const isPickup = st.groupArea === '门店自提'
    for (const m of st.members || []) {
      const id = Number(m.member_id)
      if (!Number.isFinite(id) || id <= 0 || seen.has(id)) continue
      seen.add(id)
      entries.push({ id, stop: st, member: m, isPickup })
    }
  }
  return entries
}

/** @param {{ isPickup: boolean, member: { is_delivered?: boolean } } | null | undefined} entry */
function exportFulfillmentStatus(entry) {
  if (!entry) return '无'
  if (entry.isPickup) return entry.member.is_delivered ? '已取' : '待自提'
  return entry.member.is_delivered ? '已送达' : '待送达'
}

/**
 * 套餐类型优先用会员餐段资格（午餐 / 晚餐 / 全餐）。
 * 资格缺失时按当日实际上了哪张大表兜底。
 * @param {{ member: { meal_scope?: string } } | null} lunchEntry
 * @param {{ member: { meal_scope?: string } } | null} dinnerEntry
 */
function exportMealScopeLabel(lunchEntry, dinnerEntry) {
  const raw = String(lunchEntry?.member?.meal_scope || dinnerEntry?.member?.meal_scope || '').trim()
  if (raw) return raw
  if (lunchEntry && dinnerEntry) return '全餐'
  if (dinnerEntry) return '晚餐'
  return '午餐'
}

/**
 * @param {{ stop: { sf_push_failed?: boolean, sf_push_error_msg?: string } } | null} lunchEntry
 * @param {{ stop: { sf_push_failed?: boolean, sf_push_error_msg?: string } } | null} dinnerEntry
 */
function exportSfFailCell(lunchEntry, dinnerEntry) {
  const parts = []
  if (lunchEntry?.stop?.sf_push_failed) {
    const msg = lunchEntry.stop.sf_push_error_msg || '是'
    parts.push(dinnerEntry ? `午餐${msg}` : msg)
  }
  if (dinnerEntry?.stop?.sf_push_failed) {
    const msg = dinnerEntry.stop.sf_push_error_msg || '是'
    parts.push(lunchEntry ? `晚餐${msg}` : msg)
  }
  return parts.length ? parts.join('；') : '否'
}

/**
 * 合并当日午餐大表与晚餐大表：每人一行。
 * 纯午餐、纯晚餐、全餐都在表里，套餐类型列区分；全餐不拆成两行。
 * @param {object | null | undefined} lunchSheet
 * @param {object | null | undefined} dinnerSheet
 * @param {string} deliveryDate
 */
function buildCombinedDeliveryExportRows(lunchSheet, dinnerSheet, deliveryDate) {
  const lunchEntries = sheetExportEntries(lunchSheet)
  const dinnerEntries = sheetExportEntries(dinnerSheet)
  const dinnerById = new Map(dinnerEntries.map((entry) => [entry.id, entry]))
  const lunchAreas = []
  const lunchByArea = new Map()
  for (const entry of lunchEntries) {
    const area = entry.stop.groupArea || ''
    if (!lunchByArea.has(area)) {
      lunchByArea.set(area, [])
      lunchAreas.push(area)
    }
    lunchByArea.get(area).push(entry)
  }
  const dinnerByArea = new Map()
  const dinnerAreas = []
  for (const entry of dinnerEntries) {
    const area = entry.stop.groupArea || ''
    if (!dinnerByArea.has(area)) {
      dinnerByArea.set(area, [])
      dinnerAreas.push(area)
    }
    dinnerByArea.get(area).push(entry)
  }

  const emitted = new Set()
  const out = []
  const pushRow = (lunchEntry, dinnerEntry) => {
    const anchor = lunchEntry || dinnerEntry
    if (!anchor) return
    emitted.add(anchor.id)
    if (dinnerEntry) emitted.add(dinnerEntry.id)
    const member = anchor.member
    const stop = anchor.stop
    const lunchUnits = Number(lunchEntry?.member?.daily_meal_units)
    const dinnerUnits = Number(dinnerEntry?.member?.daily_meal_units)
    const lunchStatus = exportFulfillmentStatus(lunchEntry)
    const dinnerStatus = exportFulfillmentStatus(dinnerEntry)
    let status = lunchEntry ? lunchStatus : dinnerStatus
    if (lunchEntry && dinnerEntry) status = `午餐${lunchStatus}；晚餐${dinnerStatus}`
    const areaIssue = Boolean(
      lunchEntry?.member?.area_issue ||
        lunchEntry?.stop?.has_area_issue ||
        dinnerEntry?.member?.area_issue ||
        dinnerEntry?.stop?.has_area_issue,
    )
    const missingCoords = Boolean(lunchEntry?.member?.missing_coords || dinnerEntry?.member?.missing_coords)
    const remarks = String(lunchEntry?.member?.remarks || dinnerEntry?.member?.remarks || '').trim()
    out.push({
      配送业务日: deliveryDate,
      线路分组: stop.groupArea ?? '',
      地址片区: stop.area ?? '',
      配送地址: addressLineForExcelExport(stop),
      会员ID: member.member_id,
      姓名: member.name != null ? String(member.name) : '',
      手机: member.phone != null ? String(member.phone) : '',
      plan_type: member.plan_type != null && String(member.plan_type).length ? String(member.plan_type) : '',
      套餐类型: exportMealScopeLabel(lunchEntry, dinnerEntry),
      午餐份数: lunchEntry && Number.isFinite(lunchUnits) && lunchUnits > 0 ? Math.trunc(lunchUnits) : '无',
      晚餐份数: formatDinnerPortionsCell(dinnerEntry ? dinnerUnits : null),
      备注: remarks,
      送达状态: status,
      片区待核实: areaIssue ? '是' : '否',
      无坐标: missingCoords ? '是' : '否',
      顺丰推单失败: exportSfFailCell(lunchEntry, dinnerEntry),
    })
  }

  for (const area of lunchAreas) {
    for (const lunchEntry of lunchByArea.get(area) || []) {
      pushRow(lunchEntry, dinnerById.get(lunchEntry.id) || null)
    }
    for (const dinnerEntry of dinnerByArea.get(area) || []) {
      if (emitted.has(dinnerEntry.id)) continue
      pushRow(null, dinnerEntry)
    }
  }
  for (const area of dinnerAreas) {
    if (lunchByArea.has(area)) continue
    for (const dinnerEntry of dinnerByArea.get(area) || []) {
      if (emitted.has(dinnerEntry.id)) continue
      pushRow(null, dinnerEntry)
    }
  }
  return out
}

/**
 * 导出当日需配送会员：午餐大表、晚餐大表合并，每人一行。
 * 套餐类型为午餐 / 晚餐 / 全餐。不受当前餐段页签限制。
 * 手机号有内容时只导出匹配会员；清空则为该业务日全量。
 */
async function exportSheetToExcel() {
  if (exportBusy.value) return
  const d = String(sheetToday.value.delivery_date || deliveryDateQuery.value || todayShanghaiStr()).trim()
  const phone = String(phoneQuery.value || '').trim()
  exportBusy.value = true
  try {
    const [lunchSheet, dinnerSheet] = await Promise.all([
      fetchDeliverySheetForExport(SHEET_VIEW_LUNCH, d, phone),
      fetchDeliverySheetForExport(SHEET_VIEW_DINNER, d, phone),
    ])
    const out = buildCombinedDeliveryExportRows(lunchSheet, dinnerSheet, d)
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
      { wch: 10 },
      { wch: 10 },
      { wch: 10 },
      { wch: 28 },
      { wch: 28 },
      { wch: 10 },
      { wch: 8 },
      { wch: 24 },
    ]
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, '配送清单')
    XLSX.writeFile(wb, `配送清单_${d}.xlsx`)
    showToast(`已导出 ${out.length} 行`, 'success')
  } catch (e) {
    if (handleAdminLogout(e)) {
      showToast('登录已过期，请重新登录', 'error')
      return
    }
    showToast(e instanceof Error ? e.message : '导出失败', 'error')
  } finally {
    exportBusy.value = false
  }
}

/** 打印标签：当前片区（含周卡/月卡门店自提）或全部到家；全部时按大表片区顺序逐批出纸 */
const labelPrintBusy = ref(false)

async function printDeliveryLabels(scope) {
  if (labelPrintBusy.value || printLoading.value) return
  const d = String(sheetToday.value.delivery_date || deliveryDateQuery.value || todayShanghaiStr()).trim()
  const region = scope === 'region' ? activeRegionTab.value : null
  if (scope === 'region' && !region) {
    showToast('请先选择片区', 'error')
    return
  }
  labelPrintBusy.value = true
  try {
    const cfg = await resolveScene('delivery_sheet')
    if (!cfg?.configured) {
      showToast('请先在系统管理 → 打印设置 → 配送标签 中配置打印机', 'error')
      return
    }
    const storeName =
      String(adminStoreBranding.value?.store_name || '').trim() || 'OK饭'
    const regionCodes = sheetToday.value.region_codes || {}
    const missingCodes = missingRegionCodesForStops(
      flatStops.value,
      regionCodes,
      scope === 'region' ? region : null,
    )
    if (missingCodes.length) {
      showToast(
        `以下片区未配置编码，备餐号前缀暂用 X：${missingCodes.join('、')}（请在配送区域维护编码）`,
        'error',
      )
    }

    /** 与左侧片区 Tab 顺序一致（大表 groups 顺序），逐片区发送打印任务 */
    const targetRegions =
      scope === 'all'
        ? (sheetToday.value.groups || [])
            .map((g) => g.area)
            .filter((a) => a && a !== '门店自提')
        : [region]

    let totalSheets = 0
    let failed = false
    for (const area of targetRegions) {
      if (!area) continue
      const items = buildDeliveryLabelItems(
        flatStops.value,
        d,
        area,
        addressLineForExcelExport,
        storeName,
        regionCodes,
      )
      if (!items.length) continue
      const result = await submitPrintJob('delivery_sheet', items, { silentToast: true })
      if (!result) {
        failed = true
        break
      }
      totalSheets += Number(result.printed_count) || 0
    }

    if (!totalSheets) {
      showToast('没有可打印的配送记录', 'error')
      return
    }
    if (failed) {
      showToast(`已打印 ${totalSheets} 张后中断，请检查打印机后重试剩余片区`, 'error')
      return
    }
    showToast(
      scope === 'all'
        ? `已按片区顺序发送 ${totalSheets} 张到本地打印机`
        : `已发送 ${totalSheets} 张到本地打印机`,
      'success',
    )
  } finally {
    labelPrintBusy.value = false
  }
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

/** el-table row-key：到家按停靠点 id（同址多会员拆开后地址不再唯一） */
function deliveryStopRowKey(row) {
  const g = activeRegionTab.value || ''
  if (row.stop_id) return `${g}\u0001${row.stop_id}`
  const mid = row.members && row.members[0] ? row.members[0].member_id : ''
  return `${g}\u0001${row.address_line || ''}\u0001${mid}`
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
  const stopCount = selectedDeliveryStops.value.length
  const tip = `即将批量标记 ${pendingIds.length} 位会员（${stopCount} 个配送点）。人数较多时服务器需逐条处理，反馈可能较慢，请勿关闭页面直至完成。确定继续？`
  if (!window.confirm(tip)) return
  const mealPeriod = deliveryMarkMealPeriod(sheetView.value)
  batchMarking.value = true
  const d0 = String(sheetToday.value.delivery_date || deliveryDateQuery.value || todayShanghaiStr()).trim()
  try {
    for (const memberId of pendingIds) {
      await apiJson(
        '/api/admin/delivery-mark',
        {
          method: 'POST',
          body: JSON.stringify({
            member_id: Number(memberId),
            delivery_date: d0,
            kind,
            meal_period: mealPeriod,
          }),
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

/** 行内取消勾选后，工具条「全选」跟着当前筛选结果走 */
function syncSfSelectAllFromRows() {
  const rows = sfModalFilteredRows.value.filter((row) => !row.already_pushed)
  sfSelectAll.value = rows.length > 0 && rows.every((row) => row.selected)
}

function sfPreviewRowClassName({ row }) {
  const names = []
  if (row.selected && !row.already_pushed) names.push('sf-row--on')
  if (row.recv_lng == null || row.recv_lat == null) names.push('sf-row--no-coords')
  return names.join(' ')
}

async function loadSfPreviewData() {
  if (!adminAccessToken.value) return
  sfLoading.value = true
  const d0 = (deliveryDateQuery.value || '').trim() || todayShanghaiStr()
  const base = new URLSearchParams()
  base.set('delivery_date', d0)
  const a = sfPreviewQueryArea()
  if (a) base.set('area', a)
  const ph = (phoneQuery.value || '').trim()
  if (ph) base.set('phone', ph)
  try {
    const data = await apiJson(
      `${getSfPushPreviewApiPath(sheetView.value, sfPushMode.value)}?${base.toString()}`,
      {},
      { auth: true }
    )
    const d1 = data?.delivery_date || d0
    sfPreview.value = {
      delivery_date: d1,
      rows: normalizeSfPreviewRows(data?.rows, d1),
      sf_configured: Boolean(data?.sf_configured),
      instant_sf_configured: Boolean(data?.instant_sf_configured),
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
    sfPreview.value = { delivery_date: d0, rows: [], sf_configured: false, instant_sf_configured: false }
  } finally {
    sfLoading.value = false
  }
}

async function openSfDialog(mode = SF_PUSH_MODE_SHEET) {
  if (!adminAccessToken.value) return
  sfPushMode.value = mode
  sfModalPhoneFilter.value = ''
  sfPreviewAllRegions.value = false
  sfDialogOpen.value = true
  await loadSfPreviewData()
}

async function submitSfPush() {
  if (sfPushSubmitting.value) return
  const d0 = (sfPreview.value.delivery_date || deliveryDateQuery.value || todayShanghaiStr()).trim()
  const rows = (sfPreview.value.rows || []).map((r) => ({ ...r }))
  if (!rows.length) {
    showToast('没有可推单的停靠点', 'error')
    return
  }
  if (sfPushMode.value === SF_PUSH_MODE_SHEET) {
    const err = validateSfSheetPushRows(rows, d0, sfPushHelpers)
    if (err) {
      showToast(err, 'error')
      return
    }
  }
  sfPushSubmitting.value = true
  try {
    const payload = buildSfPushPayload(rows, d0, sfPushMode.value, sfPushHelpers)
    const data = await apiJson(
      getSfPushApiPath(sfPushMode.value, sheetView.value),
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      { auth: true }
    )
    toastSfPushBatchOutcome(data, showToast, {
      successText: sfPushModeIsInstant.value ? '及时单已全部提交' : '已全部提交',
    })
    sfDialogOpen.value = false
    await fetchSheet()
  } catch (e) {
    toastSfPushError(e instanceof Error ? e.message : '推单失败', showToast)
    // 后端可能在 HTTP 500 前已落库推单（如大批量推单末尾异常），仍刷新大表
    await fetchSheet()
  } finally {
    sfPushSubmitting.value = false
  }
}

async function markDelivery(memberId, kind) {
  if (batchMarking.value || markingMemberId.value != null) return
  const d0 = String(sheetToday.value.delivery_date || deliveryDateQuery.value || todayShanghaiStr()).trim()
  const mealPeriod = deliveryMarkMealPeriod(sheetView.value)
  markingMemberId.value = memberId
  try {
    await apiJson(
      '/api/admin/delivery-mark',
      {
        method: 'POST',
        body: JSON.stringify({
          member_id: Number(memberId),
          delivery_date: d0,
          kind,
          meal_period: mealPeriod,
        }),
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

/** 推单后取消请假默认不加回；极端情况由客服补进当日大表 */
async function reinstatePhoneToSheet() {
  const phone = (phoneQuery.value || '').trim()
  if (!phone) {
    showToast('请先输入手机号', 'error')
    return
  }
  if (sheetView.value === SHEET_VIEW_LUNCH_DINNER) {
    showToast('请切换到「午餐」或「晚餐」Tab 后再补进', 'error')
    return
  }
  const mealPeriod = deliveryMarkMealPeriod(sheetView.value)
  reinstateBusy.value = true
  try {
    await apiJson(
      '/api/admin/delivery-sheet/reinstate-member',
      {
        method: 'POST',
        body: JSON.stringify({
          phone,
          delivery_date: (deliveryDateQuery.value || todayShanghaiStr()).trim(),
          meal_period: mealPeriod,
        }),
      },
      { auth: true },
    )
    showToast('已补进今日配送大表', 'success')
    await fetchSheet()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '补进失败', 'error')
  } finally {
    reinstateBusy.value = false
  }
}
</script>

<template>
  <section class="tab-content animate-up delivery-view">
    <!-- defer：Teleport 目标在 AdminLayout #delivery-header-toolbar，须等 layout 挂载后再解析 -->
    <Teleport defer to="#delivery-header-toolbar">
      <!-- Teleport 到 layout 后主卡 .delivery-view 不是祖先，须在卡片上重复定义 --dv-* 变量，否则会丢底色/主色 -->
      <div class="delivery-header-toolbar-card no-print">
        <div class="delivery-top-toolbar">
        <div class="delivery-top-toolbar__filters">
        <label class="delivery-field delivery-field--toolbar">
          <span class="delivery-field-label">配送业务日</span>
          <div class="delivery-biz-day-row">
            <el-date-picker
              v-model="deliveryDateQuery"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              :disabled="loading"
              :clearable="true"
              class="delivery-el-date delivery-el-date--toolbar"
              @change="fetchSheet"
            />
            <div class="delivery-biz-day-nav" role="group" aria-label="切换配送业务日">
              <button
                type="button"
                class="delivery-btn delivery-btn--outline delivery-btn--day-step"
                :disabled="loading"
                @click="shiftDeliveryBizDayBy(-1)"
              >
                上一天
              </button>
              <button
                type="button"
                class="delivery-btn delivery-btn--outline delivery-btn--day-step"
                :disabled="loading"
                @click="shiftDeliveryBizDayBy(1)"
              >
                下一天
              </button>
            </div>
          </div>
        </label>
        <label class="delivery-field delivery-field--toolbar delivery-field--toolbar-grow">
          <span class="delivery-field-label">客户搜索</span>
          <div class="delivery-search-row delivery-search-row--toolbar">
            <el-input
              v-model="phoneQuery"
              placeholder="手机后四位或完整号码"
              clearable
              :disabled="loading"
              class="delivery-el-phone delivery-el-phone--search delivery-el-phone--toolbar"
              @clear="fetchSheet"
              @keyup.enter="fetchSheet"
            >
              <template #prefix>
                <Search class="delivery-search-icon" :size="16" stroke-width="2" aria-hidden="true" />
              </template>
            </el-input>
            <button
              type="button"
              class="delivery-btn delivery-btn--outline delivery-search-submit"
              :disabled="loading"
              @click="fetchSheet"
            >
              查询
            </button>
          </div>
        </label>
        </div>
        <div class="delivery-top-toolbar__actions">
        <button
          type="button"
          class="delivery-btn delivery-btn--outline"
          :disabled="loading"
          @click="fetchSheet"
        >
          <RefreshCw :size="16" stroke-width="2" :class="{ spin: loading }" />
          数据刷新
        </button>
        <button
          type="button"
          class="delivery-btn delivery-btn--outline"
          :disabled="loading || exportBusy"
          title="导出该业务日需配送的午餐、晚餐、全餐会员，每人一行，按套餐类型区分。填写手机号时只导出匹配会员"
          @click="exportSheetToExcel"
        >
          <FileDown :size="16" stroke-width="2" />
          {{ exportBusy ? '导出中…' : '导出 Excel' }}
        </button>
        <button
          type="button"
          class="delivery-btn delivery-btn--outline"
          :disabled="loading || printLoading || labelPrintBusy || !flatStops.length"
          :title="
            activeRegionTab === '门店自提'
              ? '打印周卡/月卡门店自提备餐标签'
              : '打印当前片区标签'
          "
          @click="printDeliveryLabels('region')"
        >
          <Printer :size="16" stroke-width="2" />
          打印当前片区
        </button>
        <button
          type="button"
          class="delivery-btn delivery-btn--outline"
          :disabled="loading || printLoading || labelPrintBusy || !flatStops.length"
          title="按片区顺序逐批打印当日全部到家标签"
          @click="printDeliveryLabels('all')"
        >
          <Printer :size="16" stroke-width="2" />
          打印全部
        </button>
        <button
          type="button"
          class="delivery-btn delivery-btn--outline"
          :disabled="loading"
          title="打印当天大表上持有未核销礼品券的会员标签，勾选后自动核销"
          @click="giftCouponDialogVisible = true"
        >
          <Gift :size="16" stroke-width="2" />
          今日礼品券
        </button>
        <button
          type="button"
          class="delivery-btn delivery-btn--sf"
          :disabled="loading || !sfPushEnabledForView"
          :title="
            !sfPushEnabledForView
              ? '午晚餐视图仅运维双餐段会员；推顺丰请切换午餐或晚餐 Tab'
              : !sfPreview.sf_configured
                ? '请在后端 .env 配置顺丰开发者参数'
                : ''
          "
          @click="openSfDialog(SF_PUSH_MODE_SHEET)"
        >
          <Truck :size="16" stroke-width="2.5" />
          {{ sheetView === SHEET_VIEW_DINNER ? '顺丰晚餐推单' : '顺丰推单' }}
        </button>
        <button
          type="button"
          class="delivery-btn delivery-btn--sf-instant"
          :disabled="loading || !sfPushEnabledForView"
          :title="
            !sfPushEnabledForView
              ? '午晚餐视图仅运维双餐段会员；推顺丰请切换午餐或晚餐 Tab'
              : '勾选部分停靠点，推送到及时单账号（立即创单）；需先在门店设置配置「零售推顺丰店铺ID」'
          "
          @click="openSfDialog(SF_PUSH_MODE_INSTANT)"
        >
          <Zap :size="16" stroke-width="2.5" />
          推送及时单
        </button>
        </div>
        </div>
      </div>
    </Teleport>

    <div class="delivery-page no-print">
      <!-- 左侧：今日需备单量（毛玻璃主卡）；右侧：片区点选 -->
      <div class="delivery-stats-and-areas">
        <div class="delivery-hero-card delivery-hero-card--stats-left">
          <aside class="delivery-stats-panel" aria-label="今日需备单量">
            <div class="delivery-stats-panel__glow" aria-hidden="true" />
            <div class="delivery-stats-panel__body delivery-stats-line">
              <span
                v-if="deliveryQueryIsTodayShanghai"
                class="delivery-stats-panel__badge"
              >今日实时</span>
              <p class="delivery-stats-panel__kicker">今日需备单量</p>
              <div class="delivery-stats-metric">
                <strong>{{ displayHomeMealTotal }}</strong>
                <span>份</span>
              </div>
              <div class="delivery-stats-follow" aria-label="自提单">
                <span class="delivery-stats-follow__label">自提单</span>
                <b>{{ displayPickupMealTotal }}</b>
                <em>份</em>
              </div>
              <div class="delivery-stats-follow" aria-label="配送点">
                <span class="delivery-stats-follow__label">配送点</span>
                <b>{{ displayStopCount }}</b>
                <em>个</em>
              </div>
            </div>
          </aside>
        </div>

        <div
          v-if="!loading && sheetToday.groups?.length"
          class="delivery-areas-card delivery-areas-card--beside-stats"
        >
          <div class="delivery-areas-card__head">
            <span class="delivery-areas-card__title">片区快速过滤</span>
            <span class="delivery-areas-card__count">{{ sheetToday.groups.length }} 个片区</span>
          </div>
          <div class="delivery-tablist-scroll custom-scrollbar" role="tablist" aria-label="配送片区">
            <button
              v-for="group in sheetToday.groups"
              :key="'t-tab-' + group.area"
              type="button"
              role="tab"
              class="delivery-region-tab"
              :class="{
                'delivery-region-tab--active': activeRegionTab === group.area,
                'delivery-region-tab--warn': group.has_area_issue || group.has_sf_push_issue,
              }"
              :aria-selected="activeRegionTab === group.area"
              @click="activeRegionTab = group.area"
            >
              <span class="delivery-region-tab__label">{{ group.area }}</span>
              <span class="delivery-region-tab__meta">
                <template v-if="group.area === '门店自提'">{{ groupTabMetaLine(group) }}</template>
                <template v-else>
                  {{ group.meal_total ?? 0 }}份 · {{ group.stop_count ?? 0 }}点 ·
                  <em>待{{ group.pending_meal_total ?? group.meal_total ?? 0 }}</em>
                </template>
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <OkfoodAdminDialogShell
      v-model:open="sfDialogOpen"
      :title="sfDialogTitle"
      :subtitle="sfDialogSubtitle"
      dlg-class="okfood-admin-dlg--sf-push"
      :close-disabled="sfPushSubmitting"
      :close-on-backdrop="!sfPushSubmitting"
    >
      <p v-if="!sfLoading && !sfDialogConfigured" class="sf-warn">
        <template v-if="sfPushModeIsInstant">
          未配置及时单账号：请在「门店设置」填写 <strong>零售推顺丰店铺ID</strong>，并确保租户对接或 .env 已配置顺丰开发者 ID、密钥及取件电话/地址。
        </template>
        <template v-else>
          未配置顺丰账号：请在 API 的 .env 中设置 <code>SF_OPEN_DEV_ID</code>、<code>SF_OPEN_SHOP_ID</code>、<code>SF_OPEN_SECRET</code> 以及
          <code>SF_PICKUP_PHONE</code>、<code>SF_PICKUP_ADDRESS</code>（取货电话与取货地址）。
        </template>
      </p>
      <p v-if="sfLoading" class="members-loading">加载推单清单…</p>
      <template v-else>
        <p v-if="!sfPushModeIsInstant && sfBizDayPast" class="sf-warn sf-warn--muted">
          当前业务日早于今日：期望送达已按今日起算，日历不可选今日之前；预约时间须晚于当前时刻。
        </p>
        <div class="sf-ctx" aria-label="本次推单范围">
          <div class="sf-ctx__item">
            <span class="sf-ctx__k">业务日</span>
            <b class="sf-ctx__v">{{ sfPreview.delivery_date || deliveryDateQuery || '—' }}</b>
          </div>
          <div class="sf-ctx__item">
            <span class="sf-ctx__k">范围</span>
            <b class="sf-ctx__v">{{ sfPreviewScopeHint }}</b>
          </div>
          <div class="sf-ctx__item">
            <span class="sf-ctx__k">取货电话</span>
            <b class="sf-ctx__v sf-ctx__v--phone">{{ sfPickupPhoneLabel }}</b>
          </div>
          <div class="sf-ctx__item">
            <span class="sf-ctx__k">停靠点</span>
            <b class="sf-ctx__v">
              {{ sfModalFilteredRows.length }}
              <em v-if="sfModalFilterActive">/ {{ (sfPreview.rows || []).length }}</em>
            </b>
          </div>
          <div class="sf-ctx__item">
            <span class="sf-ctx__k">已勾选</span>
            <b class="sf-ctx__v">{{ sfPickedCount }}</b>
          </div>
        </div>
        <div class="sf-bar">
          <div class="sf-bar__left">
            <label class="sf-check-all">
              <el-checkbox v-model="sfSelectAll" @change="() => applySfSelectAll(sfSelectAll)">
                全选
              </el-checkbox>
            </label>
            <label class="sf-check-all sf-check-all--muted">
              <el-checkbox v-model="sfPreviewAllRegions" @change="() => loadSfPreviewData()">
                加载全部片区
              </el-checkbox>
            </label>
          </div>
          <label class="sf-search">
            <span>收货手机</span>
            <el-input
              v-model="sfModalPhoneFilter"
              clearable
              placeholder="后几位或完整号"
              maxlength="20"
              size="small"
              class="sf-bar__filter-input"
              @keydown.stop
            />
          </label>
        </div>
        <div class="sf-table-wrap">
          <el-table
            v-if="(sfPreview.rows || []).length && sfModalFilteredRows.length"
            :data="sfModalFilteredRows"
            size="small"
            class="sf-table"
            max-height="480"
            :row-class-name="sfPreviewRowClassName"
          >
            <el-table-column width="48" label="选" align="center" fixed>
              <template #default="{ row }">
                <el-checkbox
                  v-model="row.selected"
                  :disabled="row.already_pushed"
                  @change="syncSfSelectAllFromRows"
                />
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
                <el-switch
                  v-if="!sfPushModeIsInstant"
                  v-model="row.push_immediately"
                  @change="onSfPushImmediatelyChange(row)"
                />
                <span v-else class="sf-instant-yes">是</span>
              </template>
            </el-table-column>
            <el-table-column v-if="!sfPushModeIsInstant" min-width="160" label="期望送达">
              <template #default="{ row }">
                <el-date-picker
                  v-model="row.expect_delivery_at"
                  type="datetime"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  :default-time="sfExpectDefaultTime"
                  :placeholder="sheetView === SHEET_VIEW_DINNER ? '默认 18:00，可改' : '默认 12:00，可改'"
                  size="small"
                  class="sf-dt"
                  :disabled="row.push_immediately"
                  :disabled-date="sfExpectDeliveryDisabledDate"
                />
              </template>
            </el-table-column>
            <el-table-column min-width="120" label="备注" show-overflow-tooltip>
              <template #default="{ row }">
                <el-input
                  v-model="row.remark"
                  size="small"
                  :class="{ 'sf-remark--has': String(row.remark || '').trim() }"
                />
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
            <el-table-column width="88" label="坐标" align="center">
              <template #default="{ row }">
                <span v-if="row.recv_lng == null || row.recv_lat == null" class="sf-bad">缺</span>
                <span v-else>有</span>
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
        <div class="sf-foot">
          <p>取消勾选则该行不推。当前将提交 <b>{{ sfPickedCount }}</b> 个停靠点。</p>
          <div class="sf-foot__actions">
            <el-button round :disabled="sfLoading || sfPushSubmitting" @click="sfDialogOpen = false">取消</el-button>
            <el-button
              round
              type="primary"
              :loading="sfPushSubmitting"
              :disabled="sfLoading || !(sfPreview.rows || []).length"
              @click="submitSfPush"
            >
              {{ sfPushModeIsInstant ? '确认推送到及时单' : '确认推送到顺丰' }}
            </el-button>
          </div>
        </div>
      </template>
    </OkfoodAdminDialogShell>

    <p v-if="loading" class="members-loading no-print">加载中…</p>

    <template v-else>
      <div class="delivery-main delivery-page delivery-page--table no-print">
        <section class="delivery-table-card">
          <header class="delivery-table-card__head">
            <div>
              <h3 class="delivery-table-card__title">
                <MapPin :size="18" stroke-width="2" class="inline-icon" aria-hidden="true" />
                配送列表（{{ sheetViewLabel }}）
                <span class="delivery-table-card__date">{{ sheetToday.delivery_date }}</span>
              </h3>
            </div>
            <el-tabs
              v-model="sheetView"
              class="delivery-sheet-view-tabs"
              @tab-change="fetchSheet"
            >
              <el-tab-pane label="午餐配送" :name="SHEET_VIEW_LUNCH" />
              <el-tab-pane label="晚餐配送" :name="SHEET_VIEW_DINNER" />
              <el-tab-pane label="午晚餐会员" :name="SHEET_VIEW_LUNCH_DINNER" />
            </el-tabs>
          </header>
          <p v-if="sheetView === SHEET_VIEW_LUNCH_DINNER" class="delivery-sheet-view-hint">
            双餐段会员运维视图；推顺丰请在「午餐」或「晚餐」分别推单。
          </p>
          <p v-if="!sheetToday.groups?.length" class="members-loading delivery-sheet-empty">
            <template v-if="sheetToday.is_subscription_delivery_day === false">
              该日非订阅配送业务日：普通周日、国家法定节假日及国务院调休放假日不生成大表，份数不计入该日（调休补班周日除外）。请选择其它业务日，或在「营业概览」核对备餐人数是否为 0。
            </template>
            <template v-else-if="(phoneQuery || '').trim()">
              该业务日无与「{{ (phoneQuery || '').trim() }}」匹配的配送记录（或该会员已请假/未在配送名单中）。
              <template v-if="sheetView !== SHEET_VIEW_LUNCH_DINNER">
                若为推单后取消请假需当日补送，可
                <button
                  type="button"
                  class="delivery-btn delivery-btn--outline delivery-reinstate-inline"
                  :disabled="loading || reinstateBusy"
                  @click="reinstatePhoneToSheet"
                >
                  {{ reinstateBusy ? '补进中…' : '补进今日配送' }}
                </button>
              </template>
            </template>
            <template v-else>
              当日暂无符合大表条件的会员（请假、未激活、余额不足、起送日晚于该日、手机号筛选无匹配等）。单点餐在「顺丰同城」预览里与订阅合并，本页仅含订阅与自提。
            </template>
          </p>
          <div v-else class="delivery-region-tabs">
            <div v-if="selectedGroup" role="tabpanel" :aria-label="selectedGroup.area" class="delivery-tabpanel">
                <div
                  class="delivery-batch-bar"
                  :class="{ 'delivery-batch-bar--on': selectedDeliveryStops.length }"
                >
                  <div class="delivery-batch-bar__left">
                    <div class="delivery-batch-bar__left-top">
                      <span class="delivery-batch-bar__pulse" aria-hidden="true" />
                      <span class="delivery-batch-bar__hint">
                        勾选配送列表，可对选中停靠点批量标记；待标记
                        <strong>{{ batchPendingMemberCount }}</strong> 位会员
                      </span>
                    </div>
                    <div v-if="batchMarking" class="delivery-batch-bar__busy" role="status" aria-live="polite">
                      <Loader2
                        :size="14"
                        stroke-width="2.25"
                        class="delivery-batch-bar__busy-ico spin"
                        aria-hidden="true"
                      />
                      <span>正在向服务器逐条提交，请稍候…</span>
                    </div>
                  </div>
                  <div class="delivery-batch-bar__right">
                    <span class="delivery-batch-bar__count">
                      已选择：<strong>{{ selectedDeliveryStops.length }}</strong> 个配送点
                    </span>
                    <div class="delivery-batch-bar__actions">
                      <button
                        type="button"
                        class="delivery-btn delivery-btn--primary delivery-batch-bar__btn"
                        :disabled="
                          loading ||
                          batchMarking ||
                          !batchPendingMemberCount ||
                          !selectedDeliveryStops.length
                        "
                        @click="markSelectedStopsDelivered"
                      >
                        <Loader2
                          v-if="batchMarking"
                          :size="15"
                          stroke-width="2.25"
                          class="delivery-batch-btn-ico spin"
                          aria-hidden="true"
                        />
                        <span>{{
                          batchMarking
                            ? '提交中…'
                            : selectedGroup.area === '门店自提'
                              ? '批量自提完成'
                              : '批量标记送达'
                        }}</span>
                      </button>
                      <button
                        type="button"
                        class="delivery-btn delivery-btn--outline delivery-batch-bar__btn"
                        :disabled="!selectedDeliveryStops.length || batchMarking"
                        @click="clearDeliverySelection"
                      >
                        清空选择
                      </button>
                    </div>
                  </div>
                </div>
                <div class="group-card__table-scroll">
                <AdminTable
                  ref="deliveryTableRef"
                  variant="delivery"
                  size="small"
                  height="100%"
                  :border="false"
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
                          :class="{ 'meal-pill-sub--wait': Number(st.pending_meal_count) > 0 }"
                        >
                          待{{ st.pending_meal_count }} · 已{{ st.delivered_meal_count }}
                        </span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="收餐目的地 / 区域" min-width="200" class-name="col-addr">
                    <template #default="{ row: st }">
                      <div class="delivery-addr-cell">
                        <div class="delivery-addr-cell__main">{{ st.address_line }}</div>
                        <div class="delivery-addr-cell__sub">
                          {{ selectedGroup?.area }}<template v-if="st.area"> · {{ st.area }}</template>
                        </div>
                        <div v-if="st.sf_push_failed" class="delivery-sf-fail-hint">
                          顺丰未推成：{{ st.sf_push_error_msg || '创单失败' }}
                        </div>
                        <div
                          v-else-if="(st.members || []).some((m) => m.missing_coords)"
                          class="delivery-sf-fail-hint"
                        >
                          地址无坐标，无法推顺丰
                        </div>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="联系人信息" min-width="160" class-name="col-contact">
                    <template #default="{ row: st }">
                      <div
                        v-for="(m, mi) in st.members"
                        :key="m.phone + mi"
                        class="contact-line"
                        :class="{ 'contact-line--area-warn': m.area_issue }"
                      >
                        <div class="contact-line__head">
                          <span class="t-name">{{ m.name }}</span>
                          <span class="delivery-status-tag" :class="deliveryMemberStatusClass(selectedGroup, m)">
                            {{ deliveryMemberStatusLabel(selectedGroup, m) }}
                          </span>
                          <span v-if="m.area_issue" class="member-area-tag">未分配片区</span>
                          <span v-if="m.missing_coords" class="member-sf-fail-tag">无坐标未推顺丰</span>
                          <span v-else-if="st.sf_push_failed" class="member-sf-fail-tag">顺丰推单失败</span>
                        </div>
                        <span class="t-sub">{{ m.phone }}</span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="配餐说明 / 备注" min-width="96" class-name="col-rmk">
                    <template #default="{ row: st }">
                      <span v-if="st.remarks_combined" class="delivery-remark-chip">{{ st.remarks_combined }}</span>
                      <span v-else class="delivery-empty-rmk">无备注说明</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="状态操作" width="132" min-width="118" class-name="col-actions" fixed="right">
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
        </section>
      </div>
    </template>

    <GiftCouponTodayDialog
      v-model:visible="giftCouponDialogVisible"
      :delivery-date="(sheetToday.delivery_date || deliveryDateQuery || '').trim()"
      :sheet-view="sheetView"
    />
  </section>
</template>

<style scoped>
/* 智能配送大表：控制台 + 单量看板 + 浅表头表格（与 2026 控制台稿对齐） */
.delivery-view {
  --dv-green: var(--el-color-primary);
  --dv-green-hover: var(--el-color-primary-dark-2);
  --dv-ink: var(--el-color-primary-dark-2);
  --dv-line: rgba(15, 23, 42, 0.06);
  --dv-ok: #1f8a5b;
  flex: 1 1 0%;
  min-width: 0;
  min-height: 0;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

/* 顶栏 Teleport 挂载点不在 .delivery-view 内，须自带变量与白底卡片，否则按钮主色丢失、整体「没底色」 */
.delivery-header-toolbar-card {
  --dv-green: var(--el-color-primary);
  --dv-green-hover: var(--el-color-primary-dark-2);
  --dv-ink: var(--el-color-primary-dark-2);
  --dv-line: rgba(15, 23, 42, 0.06);
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  /* 按卡片实际宽度换行，不按视口：侧栏占宽时主区更窄 */
  container-type: inline-size;
  container-name: delivery-toolbar;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 20px;
  box-shadow: 0 10px 30px rgba(25, 45, 55, 0.05);
}
.delivery-header-toolbar-card :deep(.el-input__wrapper) {
  box-sizing: border-box;
}
.delivery-header-toolbar-card .delivery-btn {
  min-height: 2.125rem;
}
.delivery-header-toolbar-card .delivery-btn--sf {
  color: #fff;
  background: var(--dv-green);
  border: 0;
  box-shadow: 0 8px 18px color-mix(in srgb, var(--dv-green) 32%, transparent);
}
.delivery-header-toolbar-card .delivery-btn--sf:hover:not(:disabled) {
  background: var(--dv-green-hover);
  color: #fff;
}
.delivery-header-toolbar-card .delivery-btn--sf-instant {
  color: #f7f6f3;
  background: #1d1f21;
  border: 0;
  box-shadow: none;
}
.delivery-header-toolbar-card .delivery-btn--sf-instant:hover:not(:disabled) {
  background: #33363a;
  color: #fff;
}

.delivery-page {
  /* 占满主内容区宽度；min-width:0 防止内部宽表把整页撑开 */
  width: 100%;
  max-width: 100%;
  min-width: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
}
.delivery-page--table {
  flex: 1 1 auto;
  min-height: 0;
  margin-top: 0;
  overflow: hidden;
}

.delivery-hero-card {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  padding: 22px 22px 18px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.62), rgba(255, 248, 244, 0.88));
  border: 1px solid rgba(255, 255, 255, 0.85);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 18px 40px color-mix(in srgb, var(--dv-green) 16%, transparent);
  backdrop-filter: blur(16px) saturate(1.25);
}

/* 备单量与片区同一行，高度随这一行内容 */
.delivery-stats-and-areas {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: stretch;
  min-width: 0;
  width: 100%;
}

.delivery-hero-card--stats-left {
  padding: 0;
}

.delivery-stats-panel {
  position: relative;
  display: flex;
  align-items: center;
  height: 100%;
  padding: 10px 16px;
}
.delivery-stats-panel__glow {
  position: absolute;
  width: 180px;
  height: 180px;
  right: -50px;
  top: -60px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--dv-green) 28%, transparent);
  filter: blur(28px);
  pointer-events: none;
}
.delivery-stats-panel__body {
  position: relative;
  z-index: 1;
  min-width: 0;
}
.delivery-stats-line {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.delivery-stats-panel__badge {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--dv-green) 16%, #fff);
  color: var(--dv-ink);
  font-size: 12px;
  font-weight: 700;
}
.delivery-stats-panel__kicker {
  margin: 0;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: #5c6670;
  white-space: nowrap;
}
.delivery-stats-metric {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin: 0;
  flex-shrink: 0;
}
.delivery-stats-metric strong {
  font-size: 36px;
  line-height: 1;
  letter-spacing: -0.045em;
  font-weight: 680;
  font-variant-numeric: tabular-nums;
}
.delivery-stats-metric span {
  font-size: 13px;
  color: #5c6670;
  font-weight: 700;
}
.delivery-stats-follow {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  flex-shrink: 0;
  padding: 6px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.9);
}
.delivery-stats-follow__label {
  font-size: 12px;
  font-weight: 700;
  color: #5c6670;
  white-space: nowrap;
}
.delivery-stats-follow b {
  font-size: 18px;
  line-height: 1;
  font-weight: 700;
  color: #1d1f21;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
}
.delivery-stats-follow em {
  font-style: normal;
  font-size: 12px;
  font-weight: 700;
  color: #8b949e;
}
.delivery-areas-card {
  height: 100%;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 24px;
  box-shadow: 0 10px 30px rgba(25, 45, 55, 0.05);
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.delivery-areas-card--beside-stats {
  min-width: 0;
  max-width: 100%;
}
.delivery-areas-card__head {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  flex-shrink: 0;
  padding: 0;
}
.delivery-areas-card__title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #1d1f21;
  white-space: nowrap;
}
.delivery-areas-card__count {
  font-size: 12px;
  color: #8b949e;
}
.delivery-tablist-scroll {
  flex: 1;
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
}
.delivery-region-tab {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 12px;
  border-radius: 14px;
  border: 1px solid transparent;
  background: #f6f8f9;
  color: #1d1f21;
  font: inherit;
  text-align: left;
  white-space: nowrap;
  cursor: pointer;
}
.delivery-region-tab:hover {
  background: #fff;
  border-color: var(--dv-line);
}
.delivery-region-tab--active {
  background: color-mix(in srgb, var(--dv-green) 14%, #fff);
  border-color: color-mix(in srgb, var(--dv-green) 42%, #fff);
  color: var(--dv-ink);
  box-shadow: none;
}
.delivery-region-tab--warn:not(.delivery-region-tab--active) {
  border-color: #fdba74;
  background: #fffbeb;
}
.delivery-region-tab__label {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.3;
}
.delivery-region-tab__meta {
  font-size: 11px;
  font-weight: 650;
  color: #8b949e;
  font-variant-numeric: tabular-nums;
}
.delivery-region-tab__meta em {
  font-style: normal;
  color: var(--dv-ink);
  font-weight: 800;
}
.delivery-region-tab--active .delivery-region-tab__meta {
  color: #8b949e;
}


/* 顶栏：宽屏筛选与操作同一行顶左；卡片放不下时整组换到下一行，不再把按钮挤出主区 */
.delivery-top-toolbar {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 0.5rem 0.75rem;
  width: 100%;
  min-width: 0;
}
.delivery-top-toolbar__filters,
.delivery-top-toolbar__actions {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 0.5rem 0.75rem;
  min-width: 0;
  max-width: 100%;
}
.delivery-top-toolbar__filters {
  flex: 1 1 auto;
}
.delivery-top-toolbar__actions {
  flex: 0 1 auto;
}
/* 约 1520px 起一行放不下日期、搜索和全部操作按钮 */
@container delivery-toolbar (max-width: 1520px) {
  .delivery-top-toolbar__filters,
  .delivery-top-toolbar__actions {
    flex: 1 1 100%;
  }
}
.delivery-top-toolbar .delivery-btn {
  flex: 0 0 auto;
  white-space: nowrap;
}

.delivery-field--toolbar {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  /* 日期组按内容宽，避免把中间空白撑开、把搜索顶到行尾 */
  flex: 0 1 auto;
  min-width: min(100%, 22rem);
  max-width: 100%;
}
.delivery-field--toolbar-grow {
  flex: 1 1 18rem;
  min-width: min(100%, 16rem);
  max-width: 40rem;
}

/* 顶栏文案与「上一天 / 下一天」同字号、同字重，避免小号全大写字距显得不一致 */
.delivery-field-label {
  flex-shrink: 0;
  font-size: 0.6875rem;
  font-weight: 800;
  letter-spacing: normal;
  text-transform: none;
  color: #64748b;
}

/* 业务日：日期框与上/下一天并排 */
.delivery-biz-day-row {
  display: inline-flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}
.delivery-biz-day-nav {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}
.delivery-btn--day-step {
  height: 32px;
  padding: 0 10px;
  font-size: 12px;
  border-radius: 999px;
}

.delivery-field--toolbar :deep(.delivery-el-date--toolbar) {
  width: 10.25rem;
  max-width: 100%;
}
.delivery-field--toolbar :deep(.delivery-el-phone--toolbar) {
  width: 100%;
  min-width: 0;
  max-width: none;
}
.delivery-field--toolbar :deep(.delivery-el-date .el-input__wrapper),
.delivery-field--toolbar :deep(.delivery-el-phone .el-input__wrapper) {
  border-radius: 0.75rem;
  background: #f8fafc;
  border: 1px solid var(--dv-line);
  box-shadow: none;
}
.delivery-field--toolbar :deep(.delivery-el-phone .el-input__wrapper.is-focus) {
  border-color: var(--dv-green);
}

.delivery-search-row--toolbar {
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.45rem;
  flex: 1 1 auto;
  min-width: 0;
}
.delivery-search-row--toolbar .delivery-search-submit {
  flex: 0 0 auto;
}
.delivery-search-row--toolbar :deep(.delivery-el-phone--toolbar) {
  flex: 1 1 auto;
  /* 宽度交给外层 field，避免输入框最小宽度把整行顶出卡片 */
  min-width: 0;
  width: 0;
}

.delivery-search-row {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  gap: 0.5rem;
}
.delivery-search-icon {
  color: #94a3b8;
}

.delivery-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid var(--dv-line);
  background: #fff;
  color: #1d1f21;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.delivery-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.delivery-btn--outline {
  background: #fff;
  color: #1d1f21;
  border: 1px solid var(--dv-line);
}
.delivery-btn--outline:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--dv-green) 40%, #fff);
  color: var(--dv-ink);
}
.delivery-btn--secondary,
.delivery-btn--primary,
.delivery-btn--sf {
  background: var(--dv-green);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 8px 18px color-mix(in srgb, var(--dv-green) 32%, transparent);
}
.delivery-btn--secondary:hover:not(:disabled),
.delivery-btn--primary:hover:not(:disabled),
.delivery-btn--sf:hover:not(:disabled) {
  background: var(--dv-green-hover);
  color: #fff;
}
.delivery-btn--primary:disabled {
  opacity: 1;
  color: #8b949e;
  background: #e7ebed;
  box-shadow: none;
}


.delivery-main {
  display: flex;
  flex-direction: column;
  gap: 0;
  flex: 1 1 auto;
  min-height: 0;
}
.delivery-day-block {
  padding-top: 0;
  border-top: none;
}
.delivery-region-tabs {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  gap: 0;
}
.delivery-tabpanel {
  min-width: 0;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.delivery-table-card {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 24px;
  box-shadow: 0 10px 30px rgba(25, 45, 55, 0.05);
  overflow: hidden;
  min-width: 0;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.delivery-table-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-shrink: 0;
  padding: 16px 18px 12px;
}
.delivery-table-card__title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #1d1f21;
}
.delivery-table-card__date {
  margin: 0 0 0 2px;
  font-size: 13px;
  font-weight: 650;
  color: #8b949e;
  font-variant-numeric: tabular-nums;
}
.delivery-sheet-view-tabs {
  flex-shrink: 0;
}
.delivery-sheet-view-tabs :deep(.el-tabs__header) {
  margin: 0;
}
.delivery-sheet-view-tabs :deep(.el-tabs__content) {
  display: none;
}
.delivery-sheet-view-tabs :deep(.el-tabs__nav-wrap::after),
.delivery-sheet-view-tabs :deep(.el-tabs__active-bar) {
  display: none;
}
.delivery-sheet-view-tabs :deep(.el-tabs__nav) {
  display: flex;
  padding: 3px;
  border-radius: 999px;
  background: #f3f5f6;
}
.delivery-sheet-view-tabs :deep(.el-tabs__item) {
  height: 30px;
  padding: 0 14px !important;
  border-radius: 999px;
  line-height: 30px;
  font-size: 13px;
  font-weight: 700;
  color: #5c6670;
}
.delivery-sheet-view-tabs :deep(.el-tabs__item.is-active) {
  color: #fff;
  background: var(--dv-green);
}
.delivery-sheet-view-hint {
  margin: 0 18px 12px;
  padding: 8px 12px;
  flex-shrink: 0;
  border-radius: 12px;
  background: color-mix(in srgb, var(--dv-green) 10%, #fff);
  color: var(--dv-ink);
  font-size: 12px;
  font-weight: 650;
}
.delivery-sheet-empty {
  margin: 0 18px 18px;
  padding: 28px 16px;
  border-radius: 16px;
  background: #f6f8f9;
  text-align: center;
}

.delivery-batch-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  gap: 10px 12px;
  margin: 0 12px 12px;
  padding: 10px 12px;
  background: #f6f8f9;
  border: 0;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 650;
  color: #5c6670;
}
.delivery-batch-bar--on {
  background: color-mix(in srgb, var(--dv-green) 10%, #fff);
}
.delivery-batch-bar__left {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  min-width: 0;
}
.delivery-batch-bar__left-top {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}
.delivery-batch-bar__busy {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.2rem 0 0;
  font-size: 12px;
  font-weight: 700;
  color: var(--dv-ink);
  line-height: 1.2;
}
.delivery-batch-bar__busy-ico {
  flex-shrink: 0;
  color: var(--dv-green);
}
.delivery-batch-bar__pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dv-ok);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--dv-ok) 18%, transparent);
  flex-shrink: 0;
}
.delivery-batch-bar__right {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.6rem 1rem;
}
.delivery-batch-bar__hint strong,
.delivery-batch-bar__count strong {
  color: #1d1f21;
  font-variant-numeric: tabular-nums;
}
.delivery-batch-bar__count {
  color: #5c6670;
  font-size: 13px;
}
.delivery-batch-bar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
.delivery-batch-bar__btn {
  padding: 0.38rem 0.8rem;
  font-size: 0.72rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
}
.delivery-batch-btn-ico {
  flex-shrink: 0;
}

.group-card__table-scroll {
  flex: 1 1 auto;
  min-height: 0;
  padding: 0 1.15rem 12px;
  overflow: hidden;
  max-width: 100%;
  display: flex;
  flex-direction: column;
}
.group-card__table-scroll :deep(.admin-table--delivery.el-table) {
  margin: 0;
  flex: 1 1 auto;
  min-height: 0;
}

.delivery-addr-cell__main {
  font-weight: 650;
  font-size: 13px;
  color: #1d1f21;
  line-height: 1.45;
  letter-spacing: -0.01em;
}
.delivery-addr-cell__sub {
  margin-top: 3px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0;
  text-transform: none;
  color: #8b949e;
}

.contact-line__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.group-card__table-scroll :deep(.el-table__cell.col-rmk .cell) {
  white-space: normal;
  word-break: break-word;
}
.delivery-remark-chip {
  display: inline-block;
  box-sizing: border-box;
  max-width: 100%;
  padding: 8px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.45;
  white-space: normal;
  word-break: break-word;
  background: color-mix(in srgb, var(--dv-green) 14%, #fff);
  color: var(--dv-ink);
}
.delivery-empty-rmk {
  font-size: 0.75rem;
  font-weight: 700;
  color: #cbd5e1;
}
.delivery-reinstate-inline {
  margin-left: 0.35rem;
  padding: 0.2rem 0.55rem;
  font-size: 0.75rem;
  vertical-align: baseline;
}

.sf-warn {
  margin: 0 0 0.75rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
  color: #b45309;
  background: #fffbeb;
  border-radius: 0.5rem;
}
.sf-warn--muted {
  color: #92400e;
  background: #fff7ed;
  border: 1px solid #fdba74;
}
.sf-warn code {
  font-size: 0.75rem;
}
.sf-ctx {
  display: grid;
  grid-template-columns: 1.1fr 1.3fr 1.2fr 0.9fr 0.8fr;
  margin-bottom: 12px;
  border-radius: 18px;
  background: #f7f9fa;
  overflow: hidden;
}
.sf-ctx__item {
  min-width: 0;
  padding: 12px 14px;
}
.sf-ctx__item + .sf-ctx__item {
  box-shadow: inset 1px 0 0 rgba(15, 23, 42, 0.05);
}
.sf-ctx__k {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: #5c6670;
}
.sf-ctx__v {
  display: block;
  margin-top: 3px;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
  color: #1d1f21;
}
.sf-ctx__v em {
  font-style: normal;
  font-weight: 650;
  color: var(--el-color-primary-dark-2);
}
.sf-ctx__v--phone {
  font-family: "SF Mono", "JetBrains Mono", ui-monospace, Menlo, monospace;
  font-size: 14px;
  letter-spacing: -0.02em;
}
.sf-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
  margin-bottom: 12px;
}
.sf-bar__left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.sf-check-all {
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  font-weight: 700;
}
.sf-check-all--muted {
  color: #5c6670;
  font-weight: 650;
}
.sf-search {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 4px 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: #fbfcfd;
}
.sf-search > span {
  font-size: 12px;
  font-weight: 700;
  color: #5c6670;
  white-space: nowrap;
}
.sf-bar__filter-input {
  width: 148px !important;
}
.sf-search :deep(.el-input__wrapper) {
  background: transparent;
  box-shadow: none !important;
}
.sf-instant-yes {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--el-color-primary) 16%, #fff);
  color: var(--el-color-primary-dark-2);
  font-size: 12px;
  font-weight: 700;
}
.sf-table-wrap {
  width: 100%;
  min-height: 0;
  overflow: auto;
}
.sf-table {
  min-width: 1180px;
}
.sf-num {
  width: 100% !important;
}
:deep(.sf-dt) {
  width: 100%;
}
:deep(.sf-table.el-table) {
  --el-table-border-color: #f1f4f6;
  --el-table-header-bg-color: #f6f8f9;
}
:deep(.sf-table th.el-table__cell) {
  background: #f6f8f9 !important;
  color: #5c6670;
  font-size: 12px;
  font-weight: 700;
}
:deep(.sf-table .el-table__body td.el-table__cell) {
  background: #fff;
}
:deep(.sf-table .el-input__wrapper),
:deep(.sf-table .el-input-number .el-input__wrapper) {
  border-radius: 10px;
  background: #fbfcfd;
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.08) inset;
}
:deep(.sf-table .sf-remark--has .el-input__wrapper) {
  background: color-mix(in srgb, var(--el-color-primary) 14%, #fff);
  box-shadow: none;
}
:deep(.sf-table .sf-remark--has .el-input__inner) {
  color: var(--el-color-primary-dark-2);
  font-weight: 650;
}
:deep(.sf-table .sf-row--on > td.el-table__cell) {
  background: color-mix(in srgb, var(--el-color-primary) 9%, #fff) !important;
}
:deep(.sf-table .el-table__body tr:hover > td.el-table__cell) {
  background: #fbfcfd !important;
}
:deep(.sf-table .sf-row--on:hover > td.el-table__cell) {
  background: color-mix(in srgb, var(--el-color-primary) 12%, #fff) !important;
}
.sf-bad {
  color: #c45c66;
  font-weight: 700;
}
:deep(.sf-table .sf-row--no-coords > td.el-table__cell) {
  background: #fdf2f3 !important;
}
.sf-empty {
  margin: 0;
  padding: 28px 16px;
  border-radius: 16px;
  background: #f6f8f9;
  color: #5c6670;
  font-size: 13px;
  text-align: center;
}
.sf-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.sf-foot p {
  margin: 0;
  font-size: 13px;
  color: #5c6670;
}
.sf-foot b {
  color: #1d1f21;
  font-variant-numeric: tabular-nums;
}
.sf-foot__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
@media (max-width: 980px) {
  .sf-ctx {
    grid-template-columns: 1fr 1fr;
  }
  .sf-ctx__item + .sf-ctx__item {
    box-shadow: none;
    border-top: 1px solid rgba(15, 23, 42, 0.05);
  }
  .sf-foot {
    flex-direction: column;
    align-items: stretch;
  }
}

.spin {
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.inline-icon {
  vertical-align: -0.15em;
  margin-right: 0.15rem;
  color: #64748b;
}

.col-contact {
  min-width: 0;
}
.contact-line {
  margin-bottom: 0.35rem;
  line-height: 1.35;
}
.contact-line:last-child {
  margin-bottom: 0;
}

.t-idx {
  font-size: 13px;
  font-style: normal;
  font-weight: 700;
  color: #8b949e;
  font-variant-numeric: tabular-nums;
}
.t-name { font-weight: 700; color: #1d1f21; }
.t-sub {
  display: block;
  margin-top: 3px;
  color: #5c6670;
  font-size: 12px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.meal-pill {
  display: block;
  font-weight: 700;
  font-size: 18px;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
  color: #1d1f21;
  background: none;
  line-height: 1;
}
.meal-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}
.meal-pill-sub {
  font-size: 12px;
  font-weight: 650;
  color: #8b949e;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.meal-pill-sub--wait {
  color: var(--dv-ink);
  font-weight: 700;
}
.delivery-status-tag {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.delivery-status-tag--done {
  background: #e7f6ee;
  color: var(--dv-ok);
}
.delivery-status-tag--pending {
  background: color-mix(in srgb, var(--dv-green) 16%, #fff);
  color: var(--dv-ink);
  border: 0;
}
.delivery-status-tag--pickup {
  background: #eef2ff;
  color: #3730a3;
}

.t-contact {
  font-size: 0.8rem;
  vertical-align: top;
}

.contact-line--area-warn .t-name {
  color: #c2410c;
}

.member-area-tag {
  display: inline-block;
  margin: 0;
  font-size: 9px;
  font-weight: 900;
  padding: 2px 6px;
  border-radius: 4px;
  background: #ffedd5;
  color: #c2410c;
  vertical-align: middle;
}

.member-sf-fail-tag {
  display: inline-block;
  margin: 0;
  font-size: 9px;
  font-weight: 900;
  padding: 2px 6px;
  border-radius: 4px;
  background: #fee2e2;
  color: #b91c1c;
  vertical-align: middle;
}

.delivery-sf-fail-hint {
  margin-top: 4px;
  font-size: 11px;
  font-weight: 700;
  color: #b91c1c;
  line-height: 1.35;
}

@media (max-width: 980px) {
  .delivery-view {
    height: auto;
    overflow: auto;
  }
  .delivery-page--table {
    flex: none;
    min-height: 480px;
    overflow: hidden;
  }
  .delivery-stats-and-areas,
  .delivery-table-card__head,
  .delivery-stats-line,
  .delivery-areas-card {
    display: flex;
    flex-direction: column;
    align-items: stretch;
  }
  .delivery-stats-metric strong { font-size: 36px; }
}
</style>

<style>
/* 全局打印：隐藏侧栏与顶栏 */
@media print {
  .admin-layout .sidebar,
  .admin-top-tab-bar,
  .admin-delivery-toolbar-host,
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
  .delivery-view,
  .delivery-page--table,
  .group-card__table-scroll {
    height: auto !important;
    overflow: visible !important;
  }
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  padding: 0 12px;
  border: 0;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  color: #fff;
  background: var(--el-color-primary);
  box-shadow: 0 6px 14px color-mix(in srgb, var(--el-color-primary) 28%, transparent);
}
.btn-delivery-mark:hover:not(:disabled) {
  background: var(--el-color-primary-dark-2);
  color: #fff;
}
.btn-delivery-mark:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.delivery-action-done {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #1f8a5b;
  background: transparent;
  padding: 0;
}
</style>
