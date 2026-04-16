<script setup>
import { useToast } from './composables/useToast.js'

const { toastOpen, toastText, toastKind } = useToast()
</script>

<template>
  <router-view />
  <Transition name="toast-fade">
    <div
      v-if="toastOpen"
      class="app-toast"
      :class="{ 'app-toast--error': toastKind === 'error' }"
      :role="toastKind === 'error' ? 'alert' : 'status'"
    >
      {{ toastText }}
    </div>
  </Transition>
</template>
