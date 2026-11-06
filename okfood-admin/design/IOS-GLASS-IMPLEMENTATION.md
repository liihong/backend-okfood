# iOS 毛玻璃方向 · 工程落地规则（okfood-admin）

> 视觉讨论稿：`VISUAL-DIRECTION-IOS-GLASS.md` · 静态预览：`okfood-admin-theme-preview-ios-glass.html`  
> 本文件只约束 **如何在 Vue / Element Plus 里落地**，不重复阐述美学讨论。

## 1. 适用范围与阶段

| 阶段 | 范围 | 说明 |
|------|------|------|
| **Phase 1（当前）** | 壳层（`AdminLayout`）、Dashboard 首页轻量对齐 | 毛玻璃、主色三套、顶栏信息区交互与层级；**不改**业务组件 API、不改后端字段 |
| Phase 2 | 各业务列表/表单页 | 保持 **表格/表单实底**，仅统一间距与 token |
| Phase 3 | 全局插画/侧栏水果 SVG 资产化 | 预览稿 SVG 已抽为 `src/components/OkfoodNavFruitIcon.vue`（侧栏）；后续可再沉淀为共享资产或 sprite |

**原则：** 现有 `okfood-admin/.cursorrules`（Element Plus、最小改动、`showToast` 等）**优先**；本方向是**增量约定**，冲突时以 `.cursorrules` 的数据与交互硬约束为准。

## 2. 真源（Single source of truth）

1. **色与层级气质**：以 `VISUAL-DIRECTION-IOS-GLASS.md` 的 token 表 + `COLOR-PRIMARY-CANDIDATES.md` 为准。  
2. **布局与交互示意**：以 `okfood-admin-theme-preview-ios-glass.html` 为准（仅讨论稿，非运行时代码）。  
3. **运行时代码**：`src/assets/admin-ui.css` + `src/layouts/AdminLayout.vue`；新工具类加在 `admin-ui.css` 或 `scoped` 中**小而命名清晰**的块，避免复制预览 HTML 整段内联样式。

## 3. 三套主色（默认蜜桃珊瑚）

| Key | 说明 | 主色 Hex |
|-----|------|-----------|
| `primary-peach` | **默认** | `#E8927C` |
| `primary-mojito` | 备选 | `#5CBF8E` |
| `primary-iris` | 备选 | `#8B7EC8` |

**落地：** `src/assets/element-plus-okfood-theme.css` 通过 `html[data-admin-theme="primary-*"]` 覆盖 `--el-color-primary`、侧栏浅色毛玻璃与菜单选中 `--okfood-sidebar-*`、表头 `--okfood-el-table-header-*`。**持久化**：`localStorage` 键 **`okfood-admin-primary-theme`**；首屏在 `src/main.js` 写入 `document.documentElement` 以防闪烁。可与设计预览键 `okfood-admin-ios-glass-primary-theme` 互读（仅 Peach / Mojito / Iris 三套）。

## 4. 材质分级（强制）

| 区域 | 材质 | 禁止 |
|------|------|------|
| 顶栏、侧栏顶区 | 可用毛玻璃（高不透明度、`backdrop-filter` 适度） | 大面积强模糊 + 半透明正文 |
| Dashboard：最多 **1～2 张** KPI / 摘要卡 | 可选用毛玻璃或淡渐变玻璃 | 所有 KPI 一排全玻璃 |
| 表格、密集表单、校验提示 | **实色 / 极浅实底** | 整块表区域 `blur(40px)` |

## 5. 壳层布局（与预览对齐）

- **顶栏通条**：`admin-top-tab-bar` 为 **视口全宽 `fixed`**；左侧为 **品牌 + 侧栏折叠**，中间为 **页签**，右侧为 **通知 / 时钟 / 用户**。侧栏仅含 `el-menu`，`top` 与主内容区一致，视觉上与下方 KPI 卡片顶对齐。当前页标题可由内容区自管（`hidePageTitle` 等路由约定不变）。  
- **顶栏不放**：页面说明长文案、与当前页强绑定的「导出/保存」主操作（ those 放在 **主内容区** 标题行右侧）。  
- **系统消息**：顶栏铃铛 `el-popover`，`popper-class="admin-system-notifications-popover"`，与壳层同款 **iOS 玻璃**（圆角、blur、主色淡晕）；列表项为**嵌套玻璃卡**，底部操作区为 **capsule 主次按钮**（与讨论稿一致）。  
- **用户区**：`ElDropdown`（或等价）；**主题色** 为分组标题，三套主色为**同一面板内缩进**的三级项（不使用嵌套 `ElDropdown` 侧向浮层）；其下为**系统设置**、**修改密码**、**退出**。勿在顶栏常驻单独「退出」按钮。  
- **堆叠顺序**：顶栏为 `fixed` 时须 **z-index 高于** 主内容 scroll 容器，避免页内大面积内容盖住顶栏或下拉（见 `VISUAL-DIRECTION-IOS-GLASS.md` 表格「顶栏 · 下拉」）。Popper 默认 teleport 到 body 时仍须注意不要与全局 loading 层冲突。

## 6. 侧栏图标

- 预览中为 **多巴胺水果 SVG + 玻璃方底**；已落地为 `OkfoodNavFruitIcon` + `element-plus-okfood-theme.css` 中 `.okfood-nav-icon`，与 `AdminLayout` 各菜单项一一对应。  
- 每入口一色相、与 `primary` token 协调，**彩只在小格子里**；无门店 Logo 时 logo 格使用蓝莓占位，与「营业概览」同源。

## 7. Element Plus 与项目习惯

- 轻提示：**统一**为 iOS 玻璃 + 左侧状态格 + 标题/副文：`showToast`（`composables/useToast.js` + `App.vue` + `admin-ui.css` 中 `.app-toast`）。极少量 `ElMessage.*` 由 `okfood-el-glass-message.css` 覆盖为同款外观。  
- 提示：`showToast`；二次确认：`ElMessageBox.confirm`（弹窗形态，非通条 toast）。  
- 表格行选中、抽屉等继续沿用现有 EP 模式；毛玻璃只作为 **可选装饰类**，不替代 EP 组件结构。  
- **禁止** `window.alert` / `window.confirm`（与 `.cursorrules` 一致）。

## 8. Dashboard（Phase 1）微调范围（供下一步实现）

- **仅允许**：根容器类名与布局间距对齐（如 `page-content-shell`）、与壳层标题策略一致的小调整；可选给顶区统计块增加**有限**的玻璃/阴影类（不重构数据流）。  
- **禁止**：重写 `DeliveryRegionsOverviewPanel` 数据获取逻辑、改动 `dashboard-summary` 字段消费方式、无需求地替换表格/卡片为全新结构。

## 9. 变更记录

| 日期 | 说明 |
|------|------|
| 2025-11-06 | 初版：壳层 + Dashboard Phase 1 边界与 EP 约束 |
| 2025-11-06 | 侧栏对齐预览：浅色毛玻璃、水果图标组件、画布 mesh |

---

若与产品定稿冲突，以产品定稿为准，并回写本节与 `VISUAL-DIRECTION-IOS-GLASS.md`。
