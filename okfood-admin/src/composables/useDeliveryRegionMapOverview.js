import { ref, computed } from 'vue'
import { apiJson, adminAccessToken } from '../admin/core.js'
import { assignAreaForCoords, UNASSIGNED_AREA_LABEL } from '../utils/regionAssignment.js'

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
  const error = ref(null)

  async function load() {
    if (!adminAccessToken.value) return
    loading.value = true
    error.value = null
    try {
      const data = await apiJson('/api/admin/delivery-region-map-overview', {}, { auth: true })
      regions.value = Array.isArray(data?.regions) ? data.regions : []
      members.value = Array.isArray(data?.members) ? data.members : []
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败'
      regions.value = []
      members.value = []
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
    const byId = regionColorById.value
    return members.value.map((m) => {
      const lng = m.lng != null ? Number(m.lng) : null
      const lat = m.lat != null ? Number(m.lat) : null
      if (lng == null || lat == null || Number.isNaN(lng) || Number.isNaN(lat)) {
        return {
          ...m,
          plotStatus: 'no_coords',
          markerColor: '#94a3b8',
          expectedArea: null,
        }
      }
      const expected = assignAreaForCoords(lng, lat, act)
      const actual = String(m.area || '').trim() || UNASSIGNED_AREA_LABEL
      const exp = String(expected || '').trim() || UNASSIGNED_AREA_LABEL

      if (exp === actual) {
        const rid = act.find((r) => r.name === exp)?.id
        const col =
          exp === UNASSIGNED_AREA_LABEL
            ? '#64748b'
            : rid != null && byId[rid]
              ? byId[rid]
              : '#22c55e'
        return { ...m, plotStatus: 'matched', markerColor: col, expectedArea: exp }
      }
      if (exp === UNASSIGNED_AREA_LABEL && actual !== UNASSIGNED_AREA_LABEL) {
        return { ...m, plotStatus: 'outside_assigned', markerColor: '#ef4444', expectedArea: exp }
      }
      return { ...m, plotStatus: 'mismatch', markerColor: '#f59e0b', expectedArea: exp }
    })
  })

  const stats = computed(() => {
    const pts = memberPoints.value
    return {
      total: pts.length,
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
    load,
    regionsSorted,
    activeRegionsSorted,
    regionColorById,
    memberPoints,
    stats,
    membersCountByArea,
  }
}
