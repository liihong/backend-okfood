/** 将扁平分类列表转为树（含 children） */
export function buildCategoryTree(flat) {
  const list = Array.isArray(flat) ? flat : []
  const map = new Map()
  list.forEach((c) => map.set(c.id, { ...c, children: [] }))
  const roots = []
  list.forEach((c) => {
    const node = map.get(c.id)
    if (c.parent_id != null && c.parent_id !== '') {
      const parent = map.get(c.parent_id)
      if (parent) parent.children.push(node)
      else roots.push(node)
    } else {
      roots.push(node)
    }
  })
  const sortNodes = (nodes) => {
    nodes.sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.id - b.id)
    nodes.forEach((n) => {
      if (n.children?.length) sortNodes(n.children)
    })
  }
  sortNodes(roots)
  return roots
}

/** Element Plus Cascader 选项 */
export function toCascaderOptions(nodes, { leafOnly = false } = {}) {
  return (nodes || []).map((n) => {
    const hasChildren = n.children?.length > 0
    const item = { value: n.id, label: n.name, disabled: leafOnly && hasChildren }
    if (hasChildren) item.children = toCascaderOptions(n.children, { leafOnly })
    return item
  })
}

/** 某一级分类（按 code）下的二级子类，供下拉选择 */
export function categoryChildrenByParentCode(flat, parentCode) {
  const list = Array.isArray(flat) ? flat : []
  const parent = list.find((c) => c.code === parentCode)
  if (!parent) return []
  return list
    .filter((c) => c.parent_id === parent.id && c.is_active !== false)
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.id - b.id)
}

/** 分类完整路径，如「肉类 / 鸡肉」 */
export function categoryPathLabel(categoryId, flat) {
  if (categoryId == null || categoryId === '') return '未分类'
  const list = Array.isArray(flat) ? flat : []
  const byId = new Map(list.map((c) => [c.id, c]))
  const node = byId.get(categoryId)
  if (!node) return '未知分类'
  if (node.parent_id != null) {
    const parent = byId.get(node.parent_id)
    if (parent) return `${parent.name} / ${node.name}`
  }
  return node.name
}

/** el-table 树形数据 */
export function toTableTree(flat) {
  return buildCategoryTree(flat)
}
