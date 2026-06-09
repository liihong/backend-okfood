<script setup>
defineOptions({ name: 'EntryPosterView' })
import { ref, onMounted } from 'vue'
import { apiJson, apiForm, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const storeId = ref(1)
const loading = ref(false)
const saving = ref(false)
const photoUploading = ref(false)
const photoUploadKey = ref(0)

const form = ref({
  image_url: '',
  is_active: false,
})

async function loadConfig() {
  loading.value = true
  try {
    const data = await apiJson(
      `/api/admin/marketing/entry-poster?store_id=${storeId.value}`,
      {},
      { auth: true },
    )
    if (data && typeof data === 'object') {
      form.value = {
        image_url: data.image_url || '',
        is_active: data.is_active === true,
      }
    } else {
      form.value = { image_url: '', is_active: false }
    }
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

async function onPhotoUploadChange(uploadFile) {
  const file = uploadFile?.raw
  if (!file || !file.type.startsWith('image/')) return
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  photoUploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const data = await apiForm('/api/admin/upload', fd, { auth: true })
    const url = data && typeof data.url === 'string' ? data.url.trim() : ''
    if (url) {
      form.value.image_url = url
      showToast('图片已上传', 'success')
    } else {
      showToast('上传成功但未返回地址', 'error')
    }
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '上传失败', 'error')
  } finally {
    photoUploading.value = false
    photoUploadKey.value += 1
  }
}

async function saveConfig() {
  if (!form.value.image_url?.trim()) {
    showToast('请上传海报图片', 'error')
    return
  }
  saving.value = true
  try {
    await apiJson(
      `/api/admin/marketing/entry-poster?store_id=${storeId.value}`,
      {
        method: 'PUT',
        body: JSON.stringify({
          image_url: form.value.image_url.trim(),
          is_active: Boolean(form.value.is_active),
        }),
      },
      { auth: true },
    )
    showToast('已保存', 'success')
    await loadConfig()
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadConfig()
})
</script>

<template>
  <div v-loading="loading" class="entry-poster-page">
    <div class="page-card">
      <div class="page-card__head">
        <h2 class="page-card__title">进入弹窗海报</h2>
        <p class="page-card__desc">
          用户每次进入小程序时弹出（未登录或非会员可见；已登录且已开卡会员不弹出）。建议上传竖版长图，包含「买前须知」等内容。
        </p>
      </div>

      <el-form label-width="96px" class="poster-form">
        <el-form-item label="海报图片" required>
          <el-upload
            :key="photoUploadKey"
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            @change="onPhotoUploadChange"
          >
            <div class="upload-box">
              <img v-if="form.image_url" :src="form.image_url" alt="" class="upload-preview" />
              <span v-else>{{ photoUploading ? '上传中…' : '点击上传海报图片' }}</span>
            </div>
          </el-upload>
        </el-form-item>

        <el-form-item label="启用状态">
          <el-switch v-model="form.is_active" active-text="已启用" inactive-text="已停用" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveConfig">保存配置</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.entry-poster-page {
  padding: 0;
}

.page-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.page-card__title {
  margin: 0 0 8px;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}

.page-card__desc {
  margin: 0 0 24px;
  font-size: 14px;
  color: #64748b;
  line-height: 1.6;
}

.upload-box {
  width: 280px;
  min-height: 160px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  cursor: pointer;
  overflow: hidden;
}

.upload-preview {
  width: 100%;
  max-height: 480px;
  object-fit: contain;
  display: block;
}
</style>
