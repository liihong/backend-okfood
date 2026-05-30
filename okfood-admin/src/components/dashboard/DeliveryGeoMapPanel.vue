<script setup>
import { computed, onMounted, ref } from 'vue'
import { useDeliveryRegionMapOverview } from '../../composables/useDeliveryRegionMapOverview.js'
import DeliveryOverviewMap from './DeliveryOverviewMap.vue'
import { useAnimatedInteger } from '../../composables/useAnimatedInteger.js'

defineOptions({ name: 'DeliveryGeoMapPanel' })

const amapKey = String(import.meta.env.VITE_AMAP_KEY || '').trim()
const amapSecurity = String(import.meta.env.VITE_AMAP_SECURITY_CODE || '').trim()

const {
  loading,
  error,
  load,
  regionsSorted,
  regionColorById,
  mapMemberPoints,
  memberPoints,
  storeAnchor,
  stats,
} = useDeliveryRegionMapOverview()

const storePinLegendCount = computed(() =>
  storeAnchor.value?.store_lng != null && storeAnchor.value?.store_lat != null ? 1 : 0,
)

const todayLeaveCount = computed(() => memberPoints.value.filter((p) => p.absentToday).length)

const storePinLegendAnimated = useAnimatedInteger(() => storePinLegendCount.value, { duration: 420 })
const deliveredTodayAnimated = useAnimatedInteger(() => stats.value.deliveredToday, { duration: 640 })
const pendingTodayAnimated = useAnimatedInteger(() => stats.value.pendingToday, { duration: 640 })
const todayLeaveAnimated = useAnimatedInteger(() => todayLeaveCount.value, { duration: 620 })

const showSelfPickupPoints = ref(false)
const mapPointsForDisplay = computed(() => {
  const pts = mapMemberPoints.value
  if (!showSelfPickupPoints.value) return pts
  return pts.filter((p) => p.store_pickup === true || p.store_pickup === 1)
})

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="dgm-page">
    <p v-if="loading && !regionsSorted.length" class="dgm-loading">加载配送地图…</p>
    <p v-else-if="error" class="dgm-error">{{ error }}</p>

    <div v-else class="dgm-map-shell">
      <div class="dgm-map-toolbar">
        <div class="dgm-map-toolbar-left">
          <span class="dgm-map-toolbar-live-dot" aria-hidden="true" />
          <span class="dgm-map-toolbar-title">实时地理分布 (LIVE)</span>
        </div>
        <label class="dgm-map-pickup-toggle">
          <el-checkbox v-model="showSelfPickupPoints">自提显示</el-checkbox>
        </label>
      </div>
      <div class="dgm-map-body">
        <DeliveryOverviewMap
          :amap-key="amapKey"
          :amap-security="amapSecurity"
          :regions-sorted="regionsSorted"
          :region-color-by-id="regionColorById"
          :member-points="mapPointsForDisplay"
          :store-anchor="storeAnchor"
        />
        <div class="dgm-float-legends dgm-float-legends--glass" aria-label="地图图例">
          <div class="dgm-legend-card dgm-glass-legend">
            <h4 class="dgm-legend-h">标注图例</h4>
            <ul class="dgm-legend-metrics">
              <li>
                <span class="dgm-legend-metrics-left">
                  <span class="dgm-dot dgm-dot--store" />
                  <span>门店位置</span>
                </span>
                <span class="dgm-legend-metrics-n">{{ storePinLegendAnimated }}</span>
              </li>
              <li>
                <span class="dgm-legend-metrics-left">
                  <span class="dgm-dot dgm-dot--leave" />
                  <span>今日请假</span>
                </span>
                <span class="dgm-legend-metrics-n">{{ todayLeaveAnimated }}</span>
              </li>
              <li>
                <span class="dgm-legend-metrics-left">
                  <span class="dgm-dot dgm-dot--done" />
                  <span>当日已送达</span>
                </span>
                <span class="dgm-legend-metrics-n">{{ deliveredTodayAnimated }}</span>
              </li>
              <li>
                <span class="dgm-legend-metrics-left">
                  <span class="dgm-dot dgm-dot--pending" />
                  <span>尚未送达</span>
                </span>
                <span class="dgm-legend-metrics-n">{{ pendingTodayAnimated }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.dgm-page {
  margin: 0;
  padding: 0 0 2rem;
}

.dgm-loading,
.dgm-error {
  margin: 0 0 1rem;
  font-size: 14px;
  color: #64748b;
}

.dgm-error {
  color: #b91c1c;
}

.dgm-map-shell {
  background: #fff;
  border-radius: 2.5rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: min(calc(100vh - 220px), 880px);
}

.dgm-map-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem 1rem;
  padding: 1.5rem;
  border-bottom: 1px solid #f8fafc;
  flex-shrink: 0;
}

.dgm-map-toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
}

.dgm-map-toolbar-live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  flex-shrink: 0;
}

.dgm-map-toolbar-title {
  font-size: 14px;
  font-weight: 900;
  color: #334155;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.dgm-map-pickup-toggle :deep(.el-checkbox__label) {
  font-size: 13px;
  font-weight: 700;
  color: #475569;
}

.dgm-map-pickup-toggle :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: #10b981;
  border-color: #10b981;
}

.dgm-map-body {
  position: relative;
  flex: 1;
  min-height: 500px;
  background-color: #f8fafc;
  background-image: radial-gradient(#cbd5e1 1px, transparent 1px);
  background-size: 24px 24px;
}

.dgm-map-body :deep(.delivery-overview-map) {
  border: none;
  border-radius: 0;
  height: min(calc(100vh - 280px), 900px);
  min-height: 500px;
}

.dgm-float-legends--glass {
  position: absolute;
  left: 2rem;
  bottom: 2rem;
  z-index: 400;
  width: min(17rem, calc(100% - 2rem));
  max-height: min(40vh, 320px);
  overflow-y: auto;
  pointer-events: auto;
}

.dgm-glass-legend {
  padding: 1.5rem;
  border-radius: 1.5rem;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 4px 24px rgba(15, 23, 42, 0.06);
}

.dgm-legend-h {
  margin: 0 0 0.65rem;
  padding-bottom: 0.45rem;
  border-bottom: 1px solid rgba(15, 23, 42, 0.05);
  font-size: 12px;
  font-weight: 900;
  color: #64748b;
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

.dgm-legend-metrics {
  list-style: none;
  margin: 0;
  padding: 0;
}

.dgm-legend-metrics li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  margin-bottom: 0.6rem;
}

.dgm-legend-metrics li:last-of-type {
  margin-bottom: 0;
}

.dgm-legend-metrics-left {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.dgm-legend-metrics-n {
  font-weight: 900;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.dgm-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  flex-shrink: 0;
}

.dgm-dot--store {
  background: #059669;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
}
.dgm-dot--leave {
  background: #94a3b8;
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.16);
}
.dgm-dot--done {
  background: #34d399;
  box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.18);
}
.dgm-dot--pending {
  background: #f97316;
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.18);
}
</style>
