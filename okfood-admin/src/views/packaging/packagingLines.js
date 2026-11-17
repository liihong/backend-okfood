/**
 * 打包袋按每餐一只在晚上扣，不写进用盒和标配。
 * 行上的 is_meal_bag，或耗材档案里的每餐打包袋，都从可编辑列表拿开。
 */

export const MEAL_BAG_HINT = '打包袋按每餐一只自动扣，已从可编辑行拿开。保存时不会再提交这条。'

/**
 * @param {Array<{ sku_id?: number|null, is_meal_bag?: boolean, qty_per_portion?: number }>|null|undefined} lines
 * @param {Array<{ id?: number, is_meal_bag?: boolean }>|null|undefined} skus
 * @returns {{ lines: Array, removedBag: boolean }}
 */
export function editablePackagingLines(lines, skus) {
  const bagIds = new Set(
    (skus || [])
      .filter((item) => item && item.is_meal_bag)
      .map((item) => Number(item.id)),
  )
  const editable = []
  let removedBag = false
  for (const line of lines || []) {
    const skuId = line?.sku_id
    const markedBag = Boolean(line?.is_meal_bag)
    const knownBag = skuId != null && skuId !== '' && bagIds.has(Number(skuId))
    if (markedBag || knownBag) {
      removedBag = true
      continue
    }
    editable.push({
      ...line,
      sku_id: skuId ?? null,
      qty_per_portion: line?.qty_per_portion || 1,
    })
  }
  return { lines: editable, removedBag }
}
