import { ElMessageBox } from 'element-plus'

/** MessageBox 文案转义（dangerouslyUseHTMLString 用） */
function escapeMessageBoxHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * 强制加入当天配送大表 · 二次确认（规范 ElMessageBox，非 window.confirm）
 * @param {{ name?: string, phone?: string } | null | undefined} member
 * @param {'午餐' | '晚餐'} periodLabel
 * @returns {Promise<boolean>} 用户确认返回 true
 */
export async function confirmForceReinstateDelivery(member, periodLabel) {
  const who = String(member?.name || member?.phone || '—').trim() || '—'
  const subject = `确认将 ${who} 强制加入今日${periodLabel}配送大表？`
  const detail = '仅用于推单后取消请假需当日补送；其他锁表逻辑不变。'
  try {
    await ElMessageBox.confirm(
      `<p class="okfood-message-box__subject">${escapeMessageBoxHtml(subject)}</p><p class="okfood-message-box__detail">${escapeMessageBoxHtml(detail)}</p>`,
      '强制加入当天配送大表',
      {
        customClass: 'okfood-message-box',
        confirmButtonText: '确认加入',
        cancelButtonText: '取消',
        cancelButtonClass: 'okfood-message-box__cancel',
        distinguishCancelAndClose: true,
        autofocus: 'cancel',
        dangerouslyUseHTMLString: true,
      },
    )
    return true
  } catch {
    return false
  }
}
