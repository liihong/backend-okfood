import { ref, computed } from 'vue'
import { apiJson, adminAccessToken } from '../admin/core.js'
import { assignAreaForCoords, UNASSIGNED_AREA_LABEL } from '../utils/regionAssignment.js'

/** 图钉：当日已送达 / 默认（未送达或其它） */
const MARKER_DELIVERED = '#22c55e'
const MARKER_DEFAULT = '#eab308'
/** 与营业概览卡片色一致：今日请假 / 明日请假 */
const MARKER_LEAVE_TODAY = '#e11d48'
const MARKER_LEAVE_TOMORROW = '#ea580c'

const REGION_FILL_PALETTE = [
  '#0e5a44',
  '#2563eb',
  '#d97706',
  '#7c3aed',
  '#db2777',
  '#0d9488',
  '#b45309',
  '#4f46e5',
  '#be185d',
  '#047857',
  '#1d4ed8',
  '#c2410c',
  '#6d28d9',
]

export function useDeliveryRegionMapOverview() {
  const loading = ref(false)
  const regions = ref([])
  const members = ref([])
  /** @type {import('vue').Ref<{ store_name?: string | null, store_logo_url?: string | null, store_lng?: number | null, store_lat?: number | null } | null>} */
  const storeAnchor = ref(null)
  const error = ref(null)
  /** @type {import('vue').Ref<null | 'today_leave' | 'today_prep' | 'tomorrow_leave' | 'tomorrow_prep'>} */
  const mapFilterKey = ref(null)

  function toggleMapFilter(key) {
    mapFilterKey.value = mapFilterKey.value === key ? null : key
  }

  async function load() {
    if (!adminAccessToken.value) return
    loading.value = true
    error.value = null
    try {
      const data = await apiJson('/api/admin/delivery-region-map-overview', {}, { auth: true })
      regions.value = Array.isArray(data?.regions) ? data.regions : []
      members.value = Array.isArray(data?.members) ? data.members : []
      const st = data?.store
      if (st && typeof st === 'object') {
        const ln = st.store_lng != null ? Number(st.store_lng) : null
        const lt = st.store_lat != null ? Number(st.store_lat) : null
        storeAnchor.value = {
          store_name: st.store_name != null ? String(st.store_name) : null,
          store_logo_url: st.store_logo_url != null ? String(st.store_logo_url) : null,
          store_lng: ln != null && !Number.isNaN(ln) ? ln : null,
          store_lat: lt != null && !Number.isNaN(lt) ? lt : null,
        }
      } else {
        storeAnchor.value = null
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败'
      regions.value = []
      members.value = []
      storeAnchor.value = null
    } finally {
      loading.value = false
    }
  }

  const regionsSorted = computed(() => {
    return [...regions.value].sort((a, b) => {
      const pa = Number(a.priority) || 0
      const pb = Number(b.priority) || 0
      if (pa !== pb) return pa - pb
      return (Number(a.id) || 0) - (Number(b.id) || 0)
    })
  })

  const activeRegionsSorted = computed(() =>
    regionsSorted.value.filter((r) => r.is_active !== false && r.is_active !== 0),
  )

  const regionColorById = computed(() => {
    const map = {}
    let i = 0
    for (const r of regionsSorted.value) {
      map[r.id] = REGION_FILL_PALETTE[i % REGION_FILL_PALETTE.length]
      i += 1
    }
    return map
  })

  const memberPoints = computed(() => {
    const act = activeRegionsSorted.value
    return members.value.map((m) => {
      const deliveredToday = m.delivered_today === true || m.delivered_today === 1
      const absentToday = m.absent_today === true || m.absent_today === 1
      const absentTomorrow = m.absent_tomorrow === true || m.absent_tomorrow === 1
      let pinColor = MARKER_DEFAULT
      if (absentToday) pinColor = MARKER_LEAVE_TODAY
      else if (absentTomorrow) pinColor = MARKER_LEAVE_TOMORROW
      else if (deliveredToday) pinColor = MARKER_DELIVERED
      const lng = m.lng != null ? Number(m.lng) : null
      const lat = m.lat != null ? Number(m.lat) : null
      if (lng == null || lat == null || Number.isNaN(lng) || Number.isNaN(lat)) {
        return {
          ...m,
          plotStatus: 'no_coords',
          markerColor: pinColor,
          expectedArea: null,
          deliveredToday,
          absentToday,
          absentTomorrow,
        }
      }
      const expected = assignAreaForCoords(lng, lat, act)
      const actual = String(m.area || '').trim() || UNASSIGNED_AREA_LABEL
      const exp = String(expected || '').trim() || UNASSIGNED_AREA_LABEL

      if (exp === actual) {
        return {
          ...m,
          plotStatus: 'matched',
          markerColor: pinColor,
          expectedArea: exp,
          deliveredToday,
          absentToday,
          absentTomorrow,
        }
      }
      if (exp === UNASSIGNED_AREA_LABEL && actual !== UNASSIGNED_AREA_LABEL) {
        return {
          ...m,
          plotStatus: 'outside_assigned',
          markerColor: pinColor,
          expectedArea: exp,
          deliveredToday,
          absentToday,
          absentTomorrow,
        }
      }
      return {
        ...m,
        plotStatus: 'mismatch',
        markerColor: pinColor,
        expectedArea: exp,
        deliveredToday,
        absentToday,
        absentTomorrow,
      }
    })
  })

  /** 默认不展示暂停配送；点击统计卡片时按请假/备餐口径筛选（与卡片含义一致，仅作用于地图标点） */
  const mapMemberPoints = computed(() => {
    const pts = memberPoints.value
    const base = pts.filter((p) => !(p.delivery_deferred === true || p.delivery_deferred === 1))
    const f = mapFilterKey.value
    if (!f) return base
    switch (f) {
      case 'today_leave':
        return base.filter((p) => p.absentToday)
      case 'today_prep':
        return base.filter((p) => !p.absentToday)
      case 'tomorrow_leave':
        return base.filter((p) => p.absentTomorrow)
      case 'tomorrow_prep':
        return base.filter((p) => !p.absentTomorrow)
      default:
        return base
    }
  })

  const stats = computed(() => {
    const pts = memberPoints.value
    const deliveredToday = pts.filter((p) => p.deliveredToday).length
    return {
      total: pts.length,
      deliveredToday,
      pendingToday: pts.length - deliveredToday,
      matched: pts.filter((p) => p.plotStatus === 'matched').length,
      mismatch: pts.filter((p) => p.plotStatus === 'mismatch').length,
      outsideAssigned: pts.filter((p) => p.plotStatus === 'outside_assigned').length,
      noCoords: pts.filter((p) => p.plotStatus === 'no_coords').length,
    }
  })

  const membersCountByArea = computed(() => {
    const counts = {}
    for (const m of members.value) {
      const a = String(m.area || UNASSIGNED_AREA_LABEL).trim() || UNASSIGNED_AREA_LABEL
      counts[a] = (counts[a] || 0) + 1
    }
    return counts
  })

  return {
    loading,
    error,
    regions,
    members,
    storeAnchor,
    load,
    regionsSorted,
    activeRegionsSorted,
    regionColorById,
    memberPoints,
    mapMemberPoints,
    mapFilterKey,
    toggleMapFilter,
    stats,
    membersCountByArea,
  }
}
