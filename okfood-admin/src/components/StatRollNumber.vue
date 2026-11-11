<script setup>
import { computed, inject, nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  /** 目标数值；没有数据时为 null，显示占位 */
  value: { default: null },
  /** 小数位数。0 表示整数，并按千分位显示 */
  digits: { type: Number, default: 0 },
  /** 紧挨数字的后缀，例如 % */
  suffix: { type: String, default: '' },
  /** 变化时从 0 再滚一遍；不传则只在挂载和会员统计令牌变化时滚 */
  replayKey: { type: Number, default: 0 },
})

/** 页面每次拉到新数据时 +1，让数字重新从 0 滚一遍 */
const rollToken = inject('memberStatsRollToken', null)

/** 是否已经从 0 滚到目标位。先无过渡停在 0，下一帧再开过渡 */
const rolling = ref(false)

const formatted = computed(() => {
  const n = props.value
  if (n == null || !Number.isFinite(n)) return ''
  const body = props.digits > 0
    ? n.toLocaleString('zh-CN', {
        minimumFractionDigits: props.digits,
        maximumFractionDigits: props.digits,
      })
    : Math.trunc(n).toLocaleString('zh-CN')
  return `${body}${props.suffix}`
})

const cells = computed(() => {
  return [...formatted.value].map((ch, index) => ({
    key: `${index}-${ch}`,
    digit: ch >= '0' && ch <= '9' ? Number(ch) : null,
    ch,
  }))
})

/** 从 0 滚到当前各位数字。先画出 0，下一帧再开过渡，避免被合成成一次到位 */
async function playFromZero() {
  rolling.value = false
  await nextTick()
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      rolling.value = true
    })
  })
}

watch(formatted, (val) => {
  if (!val) rolling.value = false
})

if (rollToken) {
  watch(rollToken, () => {
    if (formatted.value) void playFromZero()
  })
}

watch(
  () => props.replayKey,
  () => {
    if (formatted.value) void playFromZero()
  },
)

onMounted(() => {
  if (formatted.value) void playFromZero()
})

/**
 * @param {number} digit
 * @param {number} index
 */
function stripStyle(digit, index) {
  const fromRight = cells.value.length - 1 - index
  return {
    transform: rolling.value ? `translateY(-${digit}em)` : 'translateY(0)',
    transitionDelay: `${fromRight * 45}ms`,
  }
}
</script>

<template>
  <span v-if="!formatted" class="stat-roll stat-roll--idle">…</span>
  <span v-else class="stat-roll" :aria-label="formatted">
    <span class="stat-roll__visual" aria-hidden="true">
      <template v-for="(cell, index) in cells" :key="cell.key">
        <span v-if="cell.digit == null" class="stat-roll__mark">{{ cell.ch }}</span>
        <span v-else class="stat-roll__wheel">
          <span
            class="stat-roll__strip"
            :class="{ 'is-rolling': rolling }"
            :style="stripStyle(cell.digit, index)"
          >
            <span v-for="n in 10" :key="n">{{ n - 1 }}</span>
          </span>
        </span>
      </template>
    </span>
  </span>
</template>

<style scoped>
.stat-roll {
  display: inline-flex;
  align-items: center;
  height: 1em;
  /* middle：避免 inline-flex 把基线算到盒子底边，数字整段沉到文字下面 */
  vertical-align: middle;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.stat-roll--idle {
  align-items: center;
}

.stat-roll__visual {
  display: inline-flex;
  align-items: center;
  height: 1em;
}

.stat-roll__wheel {
  display: inline-block;
  height: 1em;
  overflow: hidden;
}

.stat-roll__strip {
  display: flex;
  flex-direction: column;
  transition: none;
}

.stat-roll__strip.is-rolling {
  transition: transform 0.78s cubic-bezier(0.16, 1, 0.3, 1);
}

.stat-roll__strip span,
.stat-roll__mark {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 1em;
  line-height: 1;
}

@media (prefers-reduced-motion: reduce) {
  .stat-roll__strip.is-rolling {
    transition: none;
  }
}
</style>
