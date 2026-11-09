<script setup>
/**
 * 管理端统一弹窗外壳（浅色顶栏 + meta 条 + 底栏），对齐 design 讨论稿 .dlg
 */
import { computed } from 'vue'
import { X } from 'lucide-vue-next'

const open = defineModel('open', { type: Boolean, default: false })

const props = defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  /** md 440px · wide 820px · default 560px */
  size: { type: String, default: 'default' },
  closeDisabled: { type: Boolean, default: false },
  closeOnBackdrop: { type: Boolean, default: true },
  /**
   * 内容区不单独出滚动条，弹窗随内容撑高；长列表请在区块内自行滚动（如退卡已消费明细）
   */
  fitContent: { type: Boolean, default: false },
  /** 额外挂在 .okfood-admin-dlg 上的类名（如 okfood-admin-dlg--refund-fit） */
  dlgClass: { type: [String, Array, Object], default: '' },
})

const emit = defineEmits(['close'])

const sizeClass = computed(() => {
  if (props.size === 'md') return 'okfood-admin-dlg--md'
  if (props.size === 'wide') return 'okfood-admin-dlg--wide'
  return ''
})

function requestClose() {
  if (props.closeDisabled) return
  open.value = false
  emit('close')
}

function onBackdropClick() {
  if (props.closeOnBackdrop && !props.closeDisabled) requestClose()
}
</script>

<template>
  <!-- 挂到 body：避免在 .main-body overflow:hidden 内被裁切，顶栏未遮罩、弹窗底部被挡 -->
  <Teleport to="body">
    <div
      v-if="open"
      class="okfood-admin-dialog-overlay"
      v-esc-close="requestClose"
      @click.self="onBackdropClick"
    >
      <div
        class="okfood-admin-dlg"
        :class="[sizeClass, { 'okfood-admin-dlg--fit-content': fitContent }, dlgClass]"
        role="dialog"
        aria-modal="true"
        :aria-label="title || undefined"
        @click.stop
      >
        <header class="okfood-admin-dlg__head">
          <div class="okfood-admin-dlg__head-text">
            <h2 class="okfood-admin-dlg__title">
              <slot name="title">{{ title }}</slot>
            </h2>
            <p v-if="subtitle || $slots.subtitle" class="okfood-admin-dlg__sub">
              <slot name="subtitle">{{ subtitle }}</slot>
            </p>
          </div>
          <button
            type="button"
            class="okfood-admin-dlg__close"
            aria-label="关闭"
            :disabled="closeDisabled"
            @click="requestClose"
          >
            <X :size="18" :stroke-width="2.25" aria-hidden="true" />
          </button>
        </header>
        <!-- 操作对象：由 MemberOperationContext 填入 #operation-context -->
        <div
          v-if="$slots['operation-context']"
          class="okfood-member-op-ctx"
          role="status"
          aria-live="polite"
        >
          <slot name="operation-context" />
        </div>
        <div class="okfood-admin-dlg__body">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="okfood-admin-dlg__foot">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>
