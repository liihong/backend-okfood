import { ref } from 'vue'
import { apiJson, adminAccessToken, adminStoreId, handleAdminLogout } from '../admin/core.js'
import { showToast } from './useToast.js'
import { printLocalPayload } from '../utils/print/lodopRenderer.js'
import { buildTestLabelItems } from '../utils/print/testLabelAdapter.js'

const printing = ref(false)

function storeQuery() {
  const sid = Math.max(1, Math.floor(Number(adminStoreId.value) || 1))
  return `store_id=${sid}`
}

export function useStorePrint() {
  async function resolveScene(scene) {
    if (!adminAccessToken.value) return null
    try {
      const data = await apiJson(
        `/api/admin/store-print/resolve?${storeQuery()}&scene=${encodeURIComponent(scene)}`,
        {},
        { auth: true },
      )
      return data
    } catch (e) {
      handleAdminLogout(e)
      throw e
    }
  }

  async function submitPrintJob(scene, items, extra = {}) {
    if (!items?.length) {
      showToast('没有可打印的数据', 'error')
      return null
    }
    // silentToast 仅前端使用，不可传入后端
    const { silentToast, ...jobExtra } = extra
    printing.value = true
    try {
      const body = { scene, items, ...jobExtra }
      const data = await apiJson(
        `/api/admin/store-print/jobs?${storeQuery()}`,
        { method: 'POST', body: JSON.stringify(body) },
        { auth: true },
      )
      const printedCount =
        data?.local_payload?.layouts?.length ??
        data?.printed_count ??
        items.length
      if (data?.status === 'pending_local' && data?.local_payload) {
        await printLocalPayload(data.local_payload)
        if (!silentToast) {
          showToast(`已发送 ${printedCount} 张到本地打印机`, 'success')
        }
      } else if (data?.status === 'success') {
        if (!silentToast) {
          showToast(`云打印成功，共 ${printedCount} 张`, 'success')
        }
      }
      return { ...data, printed_count: printedCount }
    } catch (e) {
      const msg = e?.message || '打印失败'
      showToast(msg, 'error')
      handleAdminLogout(e)
      return null
    } finally {
      printing.value = false
    }
  }

  async function testProfile(profileId) {
    printing.value = true
    try {
      const data = await apiJson(
        `/api/admin/store-print/profiles/${profileId}/test?${storeQuery()}`,
        { method: 'POST' },
        { auth: true },
      )
      if (data?.status === 'pending_local' && data?.local_payload) {
        await printLocalPayload(data.local_payload, { preview: true })
        showToast('已打开打印预览', 'success')
      } else {
        showToast('测试页已发送', 'success')
      }
      return data
    } catch (e) {
      showToast(e?.message || '测试打印失败', 'error')
      handleAdminLogout(e)
      return null
    } finally {
      printing.value = false
    }
  }

  async function testScenePrint({ scene, profileId, templateKey, storeName }) {
    if (!profileId) {
      showToast('请先选择打印机', 'error')
      return null
    }
    showToast('正在连接打印机…', 'success')
    const items = buildTestLabelItems(scene, templateKey, storeName)
    printing.value = true
    try {
      const data = await apiJson(
        `/api/admin/store-print/jobs?${storeQuery()}`,
        {
          method: 'POST',
          body: JSON.stringify({
            scene,
            items,
            profile_id: profileId,
            template_key: templateKey || undefined,
          }),
        },
        { auth: true },
      )
      if (data?.status === 'pending_local' && data?.local_payload) {
        const meta = await printLocalPayload(data.local_payload, {
          preview: true,
          fallbackDefaultPrinter: true,
        })
        if (meta?.fallback) {
          showToast(
            `未匹配「${meta.hint}」，已临时使用「${meta.name}」。请在打印机管理中修正 Windows 打印机名称`,
            'error',
          )
        } else {
          showToast('已打开打印预览，确认后可出纸', 'success')
        }
      } else if (data?.status === 'success') {
        showToast('测试页已发送到云打印机', 'success')
      } else {
        showToast('测试页已发送', 'success')
      }
      return data
    } catch (e) {
      showToast(e?.message || '测试打印失败', 'error')
      handleAdminLogout(e)
      return null
    } finally {
      printing.value = false
    }
  }

  return { printing, resolveScene, submitPrintJob, testProfile, testScenePrint, storeQuery }
}
