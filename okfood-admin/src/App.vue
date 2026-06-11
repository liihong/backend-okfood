<script setup>
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { useToast } from './composables/useToast.js'

const { toastOpen, toastText, toastKind } = useToast()
</script>

<template>
  <el-config-provider :locale="zhCn">
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
  </el-config-provider>
</template>
