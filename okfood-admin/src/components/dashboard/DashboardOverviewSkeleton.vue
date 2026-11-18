<script setup>
/**
 * 今日营业概览首屏骨架：对齐 DeliveryRegionsOverviewPanel 分栏布局，避免纯文案 loading。
 */
defineProps({
  /** 与概览页 PC 宽屏餐架布局一致（≥1200px 今日|明日横排） */
  pcMealShelf: { type: Boolean, default: false },
})
</script>

<template>
  <div
    class="dro-dash-layout dro-overview-skel"
    role="status"
    aria-live="polite"
    aria-busy="true"
    aria-label="正在加载营业概览"
  >
    <div class="dro-dash-meal-shelf" :class="{ 'dro-dash-meal-shelf--pc': pcMealShelf }">
      <section
        v-for="cluster in ['today', 'tomorrow']"
        :key="cluster"
        class="dro-dash-day-cluster"
        :class="
          cluster === 'today' ? 'dro-dash-day-cluster--today' : 'dro-dash-day-cluster--tomorrow'
        "
      >
        <header class="dro-dash-day-cluster__head">
          <span class="dro-skel dro-skel--pill dro-skel--w-48" />
          <span class="dro-skel dro-skel--pill dro-skel--w-72" />
          <span class="dro-skel dro-skel--pill dro-skel--w-56" />
        </header>
        <div class="dro-dash-day-cluster__grid">
          <article v-for="kpi in 2" :key="kpi" class="dro-dash-kpi-skel">
            <div class="dro-dash-kpi-skel__top">
              <span class="dro-skel dro-skel--line dro-skel--w-40" />
              <span class="dro-skel dro-skel--pill dro-skel--w-52" />
            </div>
            <div class="dro-dash-kpi-skel__main">
              <span class="dro-skel dro-skel--photo" />
              <div class="dro-dash-kpi-skel__copy">
                <span class="dro-skel dro-skel--line dro-skel--w-80" />
                <span class="dro-skel dro-skel--line dro-skel--w-60" />
                <span class="dro-skel dro-skel--line dro-skel--hero" />
              </div>
            </div>
            <div class="dro-dash-kpi-skel__pills">
              <span v-for="n in 4" :key="n" class="dro-skel dro-skel--pill dro-skel--branch" />
            </div>
            <div class="dro-dash-kpi-skel__chips">
              <span v-for="n in 3" :key="n" class="dro-skel dro-skel--chip" />
            </div>
          </article>
        </div>
      </section>
    </div>

    <section class="dro-overview-skel__dpk" aria-hidden="true">
      <div class="dro-overview-skel__dpk-bar">
        <span class="dro-skel dro-skel--line dro-skel--w-40" />
        <div class="dro-overview-skel__dpk-days">
          <span v-for="n in 3" :key="n" class="dro-skel dro-skel--kitchen-day" />
        </div>
        <span class="dro-skel dro-skel--btn" />
      </div>
      <div class="dro-overview-skel__dpk-cabins">
        <div v-for="n in 2" :key="n" class="dro-overview-skel__dpk-card">
          <span class="dro-skel dro-skel--line dro-skel--w-60" />
          <span class="dro-skel dro-skel--search" />
          <div class="dro-overview-skel__dpk-rows">
            <span v-for="row in 4" :key="row" class="dro-skel dro-skel--row" />
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dro-overview-skel {
  margin-bottom: 0.75rem;
}

.dro-dash-layout {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.dro-dash-meal-shelf {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  width: 100%;
  min-width: 0;
}

@media (min-width: 1200px) {
  .dro-dash-meal-shelf--pc {
    flex-direction: row;
    align-items: stretch;
    gap: 0.55rem;
  }
}

.dro-dash-day-cluster {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.42rem;
  padding: 0.45rem 0.55rem 0.55rem;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.65);
  background: rgba(255, 255, 255, 0.32);
  backdrop-filter: saturate(1.15) blur(12px);
  -webkit-backdrop-filter: saturate(1.15) blur(12px);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.42) inset;
}

.dro-dash-day-cluster--today {
  border-color: color-mix(in srgb, #3b82f6 34%, rgba(255, 255, 255, 0.52));
  background: color-mix(in srgb, #3b82f6 9%, rgba(255, 255, 255, 0.34));
}

.dro-dash-day-cluster--tomorrow {
  border-color: color-mix(in srgb, var(--el-color-primary) 30%, rgba(255, 255, 255, 0.55));
  background: color-mix(in srgb, var(--el-color-primary) 8%, rgba(255, 255, 255, 0.38));
}

.dro-dash-day-cluster__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.5rem;
  padding: 0 0.15rem;
}

.dro-dash-day-cluster__grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.4rem;
  min-width: 0;
}

@media (min-width: 640px) {
  .dro-dash-day-cluster__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.dro-dash-kpi-skel {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  min-height: 11.5rem;
  padding: 0.65rem 0.7rem;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background: rgba(255, 255, 255, 0.45);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.65) inset;
}

.dro-dash-kpi-skel__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.dro-dash-kpi-skel__main {
  display: flex;
  gap: 0.65rem;
  align-items: flex-start;
}

.dro-dash-kpi-skel__copy {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  min-width: 0;
}

.dro-dash-kpi-skel__pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.dro-dash-kpi-skel__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.dro-overview-skel__dpk {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.dro-overview-skel__dpk-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.65rem;
  padding: 0.75rem 0.85rem;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(10px);
}

.dro-overview-skel__dpk-days {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  gap: 0.45rem;
  min-width: 0;
}

.dro-overview-skel__dpk-cabins {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.55rem;
}

@media (min-width: 1100px) {
  .dro-overview-skel__dpk-cabins {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.dro-overview-skel__dpk-card {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  padding: 0.75rem 0.85rem;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background: rgba(255, 255, 255, 0.38);
  min-height: 10rem;
}

.dro-overview-skel__dpk-rows {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

/* —— 占位块与脉冲动画 —— */
@keyframes dro-skel-shimmer {
  0% {
    opacity: 0.45;
  }
  50% {
    opacity: 0.85;
  }
  100% {
    opacity: 0.45;
  }
}

.dro-skel {
  display: block;
  border-radius: 8px;
  background: linear-gradient(
    90deg,
    rgba(148, 163, 184, 0.22) 0%,
    rgba(148, 163, 184, 0.38) 50%,
    rgba(148, 163, 184, 0.22) 100%
  );
  background-size: 200% 100%;
  animation: dro-skel-shimmer 1.35s ease-in-out infinite;
}

.dro-skel--line {
  height: 12px;
  border-radius: 6px;
}

.dro-skel--hero {
  height: 22px;
  max-width: 7.5rem;
}

.dro-skel--pill {
  height: 20px;
  border-radius: 999px;
}

.dro-skel--branch {
  flex: 1 1 4.5rem;
  min-width: 3.5rem;
  max-width: 5.5rem;
  height: 2.25rem;
  border-radius: 12px;
}

.dro-skel--chip {
  width: 4.75rem;
  height: 2.5rem;
  border-radius: 14px;
}

.dro-skel--photo {
  width: 4.25rem;
  height: 4.25rem;
  flex-shrink: 0;
  border-radius: 14px;
}

.dro-skel--kitchen-day {
  flex: 1 1 6.5rem;
  min-width: 5.5rem;
  height: 2.75rem;
  border-radius: 12px;
}

.dro-skel--btn {
  width: 4.5rem;
  height: 2.25rem;
  border-radius: 999px;
}

.dro-skel--search {
  width: 100%;
  height: 2rem;
  border-radius: 10px;
}

.dro-skel--row {
  width: 100%;
  height: 2.35rem;
  border-radius: 10px;
}

.dro-skel--w-40 {
  width: 40%;
  max-width: 5rem;
}

.dro-skel--w-48 {
  width: 3rem;
}

.dro-skel--w-52 {
  width: 3.25rem;
}

.dro-skel--w-56 {
  width: 3.5rem;
}

.dro-skel--w-60 {
  width: 60%;
  max-width: 8rem;
}

.dro-skel--w-72 {
  width: 4.5rem;
}

.dro-skel--w-80 {
  width: 80%;
}

@media (prefers-reduced-motion: reduce) {
  .dro-skel {
    animation: none;
    opacity: 0.65;
  }
}
</style>