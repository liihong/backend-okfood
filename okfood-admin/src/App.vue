<script setup>
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { useToast } from './composables/useToast.js'

const { toastOpen, toastTitle, toastDetail, toastKind } = useToast()
</script>

<template>
  <el-config-provider :locale="zhCn">
    <router-view />
    <Transition name="toast-fade">
      <div
        v-if="toastOpen"
        class="app-toast"
        :class="`app-toast--${toastKind}`"
        :role="toastKind === 'error' ? 'alert' : 'status'"
      >
        <span class="app-toast__icon" aria-hidden="true" />
        <div class="app-toast__body">
          <strong class="app-toast__title">{{ toastTitle }}</strong>
          <p v-if="toastDetail" class="app-toast__desc">{{ toastDetail }}</p>
        </div>
      </div>
    </Transition>
  </el-config-provider>
</template>
