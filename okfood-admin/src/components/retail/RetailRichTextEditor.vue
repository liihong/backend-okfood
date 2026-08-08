<script setup>
/**
 * 商城商品详情富文本编辑器（wangEditor 5 + Element Plus 表单配套）
 */
import '@wangeditor/editor/dist/css/style.css'
import { onBeforeUnmount, shallowRef, watch } from 'vue'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import { apiForm, adminAccessToken } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

defineOptions({ name: 'RetailRichTextEditor' })

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入商品详情介绍…' },
  height: { type: String, default: '280px' },
})

const emit = defineEmits(['update:modelValue'])

const editorRef = shallowRef(null)
const html = shallowRef(props.modelValue || '')

watch(
  () => props.modelValue,
  (v) => {
    if (v !== html.value) html.value = v || ''
  },
)

watch(html, (v) => emit('update:modelValue', v || ''))

const toolbarConfig = {
  excludeKeys: ['group-video', 'fullScreen'],
}

const editorConfig = {
  placeholder: props.placeholder,
  MENU_CONF: {
    uploadImage: {
      /** 自定义上传至后台 OSS */
      async customUpload(file, insertFn) {
        if (!adminAccessToken.value) {
          showToast('请先登录', 'error')
          return
        }
        if (!file?.type?.startsWith('image/')) {
          showToast('请选择图片文件', 'error')
          return
        }
        try {
          const fd = new FormData()
          fd.append('file', file)
          const data = await apiForm('/api/admin/upload', fd, { auth: true })
          const url = data && typeof data.url === 'string' ? data.url.trim() : ''
          if (url) insertFn(url, '', url)
          else showToast('上传成功但未返回地址', 'error')
        } catch (e) {
          showToast(e instanceof Error ? e.message : '图片上传失败', 'error')
        }
      },
    },
  },
}

onBeforeUnmount(() => {
  const ed = editorRef.value
  if (ed) ed.destroy()
})
</script>

<template>
  <div class="retail-rich-editor">
    <Toolbar class="retail-rich-editor__toolbar" :editor="editorRef" :default-config="toolbarConfig" mode="default" />
    <Editor
      v-model="html"
      class="retail-rich-editor__body"
      :style="{ height }"
      :default-config="editorConfig"
      mode="default"
      @onCreated="(ed) => (editorRef = ed)"
    />
  </div>
</template>

<style scoped>
.retail-rich-editor {
  width: 100%;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 8px;
  overflow: hidden;
}
.retail-rich-editor__toolbar {
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.retail-rich-editor__body {
  overflow-y: hidden;
}
</style>
