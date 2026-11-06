<script setup>
/**
 * 侧栏菜单水果图标（与 design/okfood-admin-theme-preview-ios-glass.html 同源）
 * 每个实例用 useId 前缀化 SVG gradient id，避免同页多枚图标定义冲突。
 */
import { useId } from 'vue'

const props = defineProps({
  /** 水果键：与预览稿 .fruit-svg-* 一致 */
  fruit: {
    type: String,
    required: true,
  },
  /** 无障碍标题，可选 */
  title: {
    type: String,
    default: '',
  },
})

/** SVG defs 内 id 需全局唯一（同页多枚图标时避免冲突） */
const p = useId().replace(/[^a-zA-Z0-9]/g, '')
</script>

<template>
  <span
    class="okfood-nav-icon"
    :class="`fruit-svg-${fruit}`"
    :title="title || undefined"
    aria-hidden="true"
  >
    <!-- 1 · 蓝莓 · 营业概览 -->
    <svg
      v-if="fruit === 'blueberry'"
      class="okfood-nav-icon__svg"
      viewBox="0 0 32 32"
      focusable="false"
    >
      <defs>
        <radialGradient :id="`${p}-nav1-b1`" cx="32%" cy="30%" r="65%">
          <stop offset="0%" stop-color="#C9D4FF" />
          <stop offset="45%" stop-color="#6B7CFF" />
          <stop offset="100%" stop-color="#3A3AD4" />
        </radialGradient>
        <radialGradient :id="`${p}-nav1-b2`" cx="38%" cy="32%" r="60%">
          <stop offset="0%" stop-color="#D4DAFF" />
          <stop offset="50%" stop-color="#5B6AEE" />
          <stop offset="100%" stop-color="#3838C8" />
        </radialGradient>
        <linearGradient :id="`${p}-nav1-stem`" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#8CE06A" />
          <stop offset="100%" stop-color="#3FA82A" />
        </linearGradient>
      </defs>
      <ellipse cx="19" cy="19" rx="8.5" ry="8" :fill="`url(#${p}-nav1-b1)`" />
      <ellipse cx="13" cy="21" rx="7" ry="6.8" :fill="`url(#${p}-nav1-b2)`" />
      <ellipse cx="15.5" cy="12" rx="2.2" ry="1.4" :fill="`url(#${p}-nav1-stem)`" />
      <ellipse cx="20.5" cy="17" rx="2" ry="1.8" fill="#fff" opacity="0.35" />
      <ellipse cx="10.5" cy="19" rx="1.6" ry="1.4" fill="#fff" opacity="0.2" />
    </svg>

    <!-- 2 · 石榴 · 会员档案 -->
    <svg
      v-else-if="fruit === 'pomegranate'"
      class="okfood-nav-icon__svg"
      viewBox="0 0 32 32"
      focusable="false"
    >
      <defs>
        <radialGradient :id="`${p}-nav2-f`" cx="35%" cy="28%" r="70%">
          <stop offset="0%" stop-color="#FF8A8E" />
          <stop offset="42%" stop-color="#C41E32" />
          <stop offset="100%" stop-color="#6E0E18" />
        </radialGradient>
        <linearGradient :id="`${p}-nav2-cal`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#A83240" />
          <stop offset="100%" stop-color="#5C1018" />
        </linearGradient>
      </defs>
      <ellipse cx="16" cy="19" rx="11" ry="11" :fill="`url(#${p}-nav2-f)`" />
      <path d="M10 10 L16 6 L22 10 L20 13 L16 11 L12 13 Z" :fill="`url(#${p}-nav2-cal)`" />
      <ellipse cx="11.5" cy="16" rx="2.5" ry="2" fill="#fff" opacity="0.28" />
      <circle cx="17" cy="22" r="1.2" fill="#6E0E18" opacity="0.4" />
    </svg>

    <!-- 3 · 樱桃 · 开卡工单 -->
    <svg
      v-else-if="fruit === 'cherry'"
      class="okfood-nav-icon__svg"
      viewBox="0 0 32 32"
      focusable="false"
    >
      <defs>
        <radialGradient :id="`${p}-nav3-c`" cx="35%" cy="30%" r="68%">
          <stop offset="0%" stop-color="#FFC8F0" />
          <stop offset="45%" stop-color="#E02088" />
          <stop offset="100%" stop-color="#880858" />
        </radialGradient>
        <linearGradient :id="`${p}-nav3-stem`" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#6BC94C" />
          <stop offset="100%" stop-color="#2E8B1F" />
        </linearGradient>
      </defs>
      <path
        d="M16 7 Q18 12 22 14 Q24 15 25 12"
        :stroke="`url(#${p}-nav3-stem)`"
        stroke-width="2.2"
        fill="none"
        stroke-linecap="round"
      />
      <ellipse cx="12" cy="21" rx="6.5" ry="7" :fill="`url(#${p}-nav3-c)`" transform="rotate(-8 12 21)" />
      <ellipse cx="21" cy="22" rx="6.2" ry="6.8" :fill="`url(#${p}-nav3-c)`" transform="rotate(10 21 22)" />
      <ellipse cx="10" cy="18" rx="2" ry="1.8" fill="#fff" opacity="0.32" />
    </svg>

    <!-- 4 · 香蕉 · 订单管理 -->
    <svg
      v-else-if="fruit === 'banana'"
      class="okfood-nav-icon__svg"
      viewBox="0 0 32 32"
      focusable="false"
    >
      <defs>
        <linearGradient :id="`${p}-nav4-b`" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#FFF4A8" />
          <stop offset="40%" stop-color="#FFE24A" />
          <stop offset="100%" stop-color="#F5B014" />
        </linearGradient>
      </defs>
      <path d="M7 22 Q10 8 24 6 Q26 14 22 24 Q16 28 9 25 Q6 24 7 22 Z" :fill="`url(#${p}-nav4-b)`" />
      <path d="M9 20 Q14 10 22 9" stroke="#E8A010" stroke-width="1.2" fill="none" opacity="0.35" />
      <ellipse cx="12" cy="14" rx="3" ry="2" fill="#fff" opacity="0.45" />
    </svg>

    <!-- 5 · 火龙果 · 配送管理 -->
    <svg
      v-else-if="fruit === 'pitaya'"
      class="okfood-nav-icon__svg"
      viewBox="0 0 32 32"
      focusable="false"
    >
      <defs>
        <radialGradient :id="`${p}-nav5-p`" cx="40%" cy="35%" r="65%">
          <stop offset="0%" stop-color="#E8C8FF" />
          <stop offset="38%" stop-color="#B020D8" />
          <stop offset="100%" stop-color="#601098" />
        </radialGradient>
        <linearGradient :id="`${p}-nav5-leaf`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#9AEC6A" />
          <stop offset="100%" stop-color="#38A828" />
        </linearGradient>
      </defs>
      <ellipse cx="16" cy="20" rx="10" ry="12" :fill="`url(#${p}-nav5-p)`" />
      <path
        d="M8 12 L11 6 L14 11 L16 5 L18 11 L21 6 L24 12"
        fill="none"
        :stroke="`url(#${p}-nav5-leaf)`"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <ellipse cx="12" cy="17" rx="2.8" ry="2.2" fill="#fff" opacity="0.3" />
    </svg>

    <!-- 6 · 梨 · 数据统计 -->
    <svg
      v-else-if="fruit === 'pear'"
      class="okfood-nav-icon__svg"
      viewBox="0 0 32 32"
      focusable="false"
    >
      <defs>
        <radialGradient :id="`${p}-nav6-pe`" cx="38%" cy="25%" r="72%">
          <stop offset="0%" stop-color="#D8FFF5" />
          <stop offset="42%" stop-color="#38D4A8" />
          <stop offset="100%" stop-color="#0A9070" />
        </radialGradient>
        <linearGradient :id="`${p}-nav6-st`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#8BC752" />
          <stop offset="100%" stop-color="#4A9828" />
        </linearGradient>
      </defs>
      <path
        d="M16 9 Q22 11 22 18 Q22 26 16 28 Q10 26 10 18 Q10 11 16 9 Z"
        :fill="`url(#${p}-nav6-pe)`"
      />
      <ellipse cx="16" cy="8" rx="2" ry="3.5" :fill="`url(#${p}-nav6-st)`" />
      <ellipse cx="13" cy="15" rx="3.5" ry="4" fill="#fff" opacity="0.25" />
    </svg>

    <!-- 7 · 苹果 · 菜单管理 -->
    <svg
      v-else-if="fruit === 'apple'"
      class="okfood-nav-icon__svg"
      viewBox="0 0 32 32"
      focusable="false"
    >
      <defs>
        <radialGradient :id="`${p}-nav7-a`" cx="35%" cy="28%" r="68%">
          <stop offset="0%" stop-color="#C8FFC8" />
          <stop offset="38%" stop-color="#38C848" />
          <stop offset="100%" stop-color="#106820" />
        </radialGradient>
        <linearGradient :id="`${p}-nav7-leaf`" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#7EE060" />
          <stop offset="100%" stop-color="#2A9820" />
        </linearGradient>
      </defs>
      <path
        d="M16 8 C12 8 9 12 9 18 C9 24 12 28 16 28 C20 28 23 24 23 18 C23 12 20 8 16 8 Z"
        :fill="`url(#${p}-nav7-a)`"
      />
      <path
        d="M16 7 Q19 4 21 6"
        :stroke="`url(#${p}-nav7-leaf)`"
        stroke-width="2"
        fill="none"
        stroke-linecap="round"
      />
      <ellipse cx="13" cy="15" rx="3.2" ry="4" fill="#fff" opacity="0.3" />
    </svg>

    <!-- 8 · 橘子 · 库存管理 -->
    <svg
      v-else-if="fruit === 'orange'"
      class="okfood-nav-icon__svg"
      viewBox="0 0 32 32"
      focusable="false"
    >
      <defs>
        <radialGradient :id="`${p}-nav8-o`" cx="38%" cy="30%" r="68%">
          <stop offset="0%" stop-color="#FFE8A8" />
          <stop offset="45%" stop-color="#FF9A28" />
          <stop offset="100%" stop-color="#E86008" />
        </radialGradient>
        <linearGradient :id="`${p}-nav8-l`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#8AD84A" />
          <stop offset="100%" stop-color="#3A9810" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="18" r="11" :fill="`url(#${p}-nav8-o)`" />
      <path d="M16 7 Q14 4 11 5 Q13 8 16 9" :fill="`url(#${p}-nav8-l)`" />
      <circle cx="12" cy="15" r="1.5" fill="#fff" opacity="0.35" />
      <path
        d="M9 12 L23 24 M11 24 L21 12"
        stroke="#E87810"
        stroke-width="0.8"
        opacity="0.15"
      />
    </svg>

    <!-- 9 · 杨梅 · 小程序营销 -->
    <svg
      v-else-if="fruit === 'bayberry'"
      class="okfood-nav-icon__svg"
      viewBox="0 0 32 32"
      focusable="false"
    >
      <defs>
        <radialGradient :id="`${p}-nav9-b`" cx="35%" cy="28%" r="70%">
          <stop offset="0%" stop-color="#FFE0C8" />
          <stop offset="42%" stop-color="#FF6840" />
          <stop offset="100%" stop-color="#C02810" />
        </radialGradient>
      </defs>
      <ellipse cx="16" cy="19" rx="10" ry="10.5" :fill="`url(#${p}-nav9-b)`" />
      <circle cx="10" cy="14" r="2.2" fill="#FF8060" />
      <circle cx="22" cy="15" r="2.2" fill="#E85838" />
      <circle cx="16" cy="11" r="2" fill="#FFA078" />
      <circle cx="13" cy="22" r="2" fill="#D84828" />
      <circle cx="20" cy="23" r="2" fill="#C84020" />
      <ellipse cx="13" cy="17" rx="2.8" ry="2.2" fill="#fff" opacity="0.28" />
    </svg>

    <!-- 10 · 山竹 · 系统管理 -->
    <svg
      v-else-if="fruit === 'mangosteen'"
      class="okfood-nav-icon__svg"
      viewBox="0 0 32 32"
      focusable="false"
    >
      <defs>
        <radialGradient :id="`${p}-nav10-s`" cx="38%" cy="30%" r="68%">
          <stop offset="0%" stop-color="#E4D0FF" />
          <stop offset="45%" stop-color="#9868E8" />
          <stop offset="100%" stop-color="#5828A8" />
        </radialGradient>
        <linearGradient :id="`${p}-nav10-cal`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#6AE050" />
          <stop offset="100%" stop-color="#208818" />
        </linearGradient>
      </defs>
      <ellipse cx="16" cy="20" rx="10.5" ry="10" :fill="`url(#${p}-nav10-s)`" />
      <path d="M8 14 L10 9 L13 12 L16 8 L19 12 L22 9 L24 14 Z" :fill="`url(#${p}-nav10-cal)`" />
      <ellipse cx="12.5" cy="17" rx="2.5" ry="2" fill="#fff" opacity="0.22" />
    </svg>
  </span>
</template>
