<script setup>
/**
 * 商城商品详情富文本编辑器（wangEditor 5 + 现有 /api/admin/upload OSS）
 */
import '@wangeditor/editor/dist/css/style.css'
import { nextTick, onActivated, onBeforeUnmount, onDeactivated, shallowRef, watch, ref } from 'vue'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import { apiForm, adminAccessToken } from '../../admin/core.js'
import { compressImageFileIfNeeded } from '../../utils/compressImageFile.js'
import { showToast } from '../../composables/useToast.js'

defineOptions({ name: 'RetailRichTextEditor' })

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入商品详情介绍…' },
  height: { type: String, default: '320px' },
})

const emit = defineEmits(['update:modelValue'])

const editorRef = shallowRef(null)
const html = shallowRef(props.modelValue || '')
/** KeepAlive 切回时强制重建，避免 contenteditable 失效导致整片灰掉 */
const editorEpoch = ref(0)
const skipFirstActivate = ref(true)

watch(
  () => props.modelValue,
  (v) => {
    if (v !== html.value) html.value = v || ''
  },
)

watch(html, (v) => emit('update:modelValue', v || ''))

async function uploadDetailImage(file, insertFn) {
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  if (!file?.type?.startsWith('image/')) {
    showToast('请选择图片文件', 'error')
    return
  }
  try {
    const ready = await compressImageFileIfNeeded(file)
    const fd = new FormData()
    fd.append('file', ready)
    const data = await apiForm('/api/admin/upload', fd, { auth: true })
    const url = data && typeof data.url === 'string' ? data.url.trim() : ''
    if (url) insertFn(url, '', url)
    else showToast('上传成功但未返回地址', 'error')
  } catch (e) {
    showToast(e instanceof Error ? e.message : '图片上传失败', 'error')
  }
}

const toolbarConfig = {
  excludeKeys: ['group-video', 'fullScreen'],
}

const editorConfig = {
  placeholder: props.placeholder,
  readOnly: false,
  autoFocus: false,
  MENU_CONF: {
    uploadImage: {
      fieldName: 'file',
      maxFileSize: 20 * 1024 * 1024,
      allowedFileTypes: ['image/*'],
      customUpload: uploadDetailImage,
    },
  },
}

function destroyEditor() {
  const ed = editorRef.value
  if (!ed) return
  try {
    ed.destroy()
  } catch {
    /* 已销毁时忽略 */
  }
  editorRef.value = null
}

function handleCreated(ed) {
  editorRef.value = ed
  nextTick(() => {
    try {
      ed.enable()
    } catch {
      /* 忽略 */
    }
  })
}

onActivated(() => {
  if (skipFirstActivate.value) {
    skipFirstActivate.value = false
    return
  }
  destroyEditor()
  editorEpoch.value += 1
})

onDeactivated(() => {
  destroyEditor()
})

onBeforeUnmount(() => {
  destroyEditor()
})
</script>

<template>
  <div class="retail-rich-editor">
    <!-- Toolbar / Editor 必须一起重建，避免 KeepAlive 后工具栏和编辑区不同步 -->
    <div :key="editorEpoch">
      <Toolbar
        class="retail-rich-editor__toolbar"
        :editor="editorRef"
        :default-config="toolbarConfig"
        mode="default"
      />
      <!-- 外层固定高度，保证 wangEditor 内部 height:100% 能落到可点的编辑区 -->
      <div class="retail-rich-editor__body" :style="{ height }">
        <Editor
          v-model="html"
          class="retail-rich-editor__editor"
          :default-config="editorConfig"
          mode="default"
          @onCreated="handleCreated"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.retail-rich-editor {
  width: 100%;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.retail-rich-editor__toolbar {
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
  background: #fff;
}
.retail-rich-editor__body {
  height: 320px;
  overflow-y: hidden;
  background: #fff;
}
.retail-rich-editor__editor {
  height: 100% !important;
  overflow-y: hidden;
  background: #fff;
}
.retail-rich-editor__body :deep(.w-e-text-container),
.retail-rich-editor__body :deep(.w-e-scroll) {
  height: 100%;
  background: #fff;
}
.retail-rich-editor__body :deep([data-slate-editor]) {
  min-height: 100%;
  cursor: text;
  background: #fff;
}
.retail-rich-editor__body :deep(.w-e-text-placeholder) {
  pointer-events: none;
  color: #c0c4cc;
  font-style: normal;
}
</style>
