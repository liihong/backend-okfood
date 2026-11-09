# OK 轻食管理端 · 列表 / 弹窗 / 表头设计规范

> **状态**：会员档案相关已按本规范落地一轮；新弹窗与列表改造须先对齐本文，再在 `design/*.html` 定稿后迁正式代码。  
> **真源 CSS**：`src/assets/admin-ui.css`（弹窗壳、`okfood-mem-edit-*`、`admin-table--members` 等）  
> **真源组件**：`src/components/OkfoodAdminDialogShell.vue`、`MemberOperationContext.vue`  
> **讨论预览**：`design/okfood-admin-members-actions-preview.html`（会员「更多」操作全场景）

与 `VISUAL-DIRECTION-IOS-GLASS.md`（全局壳、色板）关系：**壳层氛围以 iOS 玻璃稿为准；会员操作弹窗与会员列表以本文为硬规范。**

---

## 1. 工作流（讨论稿 → 正式）

1. **先**在 `okfood-admin/design/` 增加或更新静态 HTML 预览（左侧场景切换），核对布局与小屏。  
2. **再**迁 Vue：业务逻辑 / 接口字段 **不重写**；只换壳与 `admin-ui.css` 类名。  
3. 样式 **优先写入 `admin-ui.css`**，组件内 `scoped` 仅补局部；禁止再新增整页 `modal-overlay` + 深绿顶栏。  
4. 讨论稿 CSS 类名（`.dlg--*`）与正式（`.okfood-admin-dlg--*`）保持一一对应，改稿时两处同步。

---

## 2. 统一弹窗外壳（OkfoodAdminDialogShell）

### 2.1 结构三层

| 层 | 含义 | 实现 |
|----|------|------|
| ① 标题区 | 办什么事 | `title` + `subtitle`（`okfood-admin-dlg__head` 白底、与壳同圆角） |
| ② 操作对象 | 对谁 | 插槽 `#operation-context` → `MemberOperationContext`（姓名 · 手机 · 餐段标签） |
| ③ 表单 + 底栏 | 具体动作 | `__body` + `#footer`（`el-button round` 取消 + 主按钮右对齐） |

### 2.2 尺寸与滚动

- `size`：`md` 440px · `default` 560px · `wide` 820px（`max-width: min(820px, 100%)`）。  
- **`fit-content`**：弹窗随内容增高；**`__body` 默认不内滚动**，超长内容由 **遮罩层** `overflow-y: auto` 滚动（避免双滚动条）。  
- **`Teleport to="body"`**：避免主内容区 `overflow: hidden` 裁切弹窗。  
- 壳层 `overflow: hidden` 保留顶栏圆角；`--addr-fit` / `--edit-fit` 仅在 body 内放开 `overflow: visible`。

### 2.3 变体（`dlgClass` / 讨论稿类名）

| 变体 | 用途 | body 内边距 | 备注 |
|------|------|-------------|------|
| `okfood-admin-dlg--addr-fit` | 送餐地址 | `12px 14px` | 双栏列表 + 编辑区；底栏常仅「关闭」 |
| `okfood-admin-dlg--edit-fit` | 修改会员 | `12px 14px` | 灰底 `#f8fafc` + 白卡片 `okfood-mem-edit-sec` |
| `okfood-admin-dlg--refund-fit` | 退卡等小屏 | 见 CSS | 仅明细区滚动；底栏固定露出 |

**左右留白**：`edit-fit` / `addr-fit` 的 **body 统一 `padding: 12px 14px`**；内容 **禁止** `max-width` + 居中（避免两侧灰带过宽）。

### 2.4 交互禁令

- 二次确认：**`ElMessageBox.confirm`** + `customClass: 'okfood-message-box'`（复用 `confirmForceReinstateDelivery.js` 等）。  
- **禁止** `window.confirm` / `window.alert`（登录过期 `alert` 等遗留除外）。  
- 危险操作：`okfood-message-box--delete` + 危险主按钮类。  
- 轻提示：`showToast`（`composables/useToast.js`）。

---

## 3. 修改会员弹窗（MemberEditModal）

### 3.1 业务逻辑（勿因 UI 改版而改）

- 晚餐区显示：`showDinnerScheduleFor(member)` — `entitled_meal_periods` 含 `dinner`、或 `dinner_balance>0`、或已暂停晚餐、或已填 `dinner_deliver_on` 任一即 true。  
- 晚餐暂停与 `dinner_deliver_on` **分开提交**；指定日期 **不自动** 勾暂停晚餐。  
- 余额 / 每日份数 / 地址 **不在本弹窗提交**（分别在「修改次数」「地址」）。

### 3.2 布局规范（2026-03 定稿）

**卡片区块**（自上而下，灰底间隙 `okfood-mem-edit-inner` gap 6～10px）：

1. **档案与套餐**（一张白卡）  
   - 一行三列等分：`repeat(3, 1fr)` — 手机号（只读）、姓名、本店会员卡。  
2. **配送与时间设置**  
   - 第一行网格：午餐 2 列等分；含晚餐 **3 列等分** — 配送片区 | 业务起送日期 | 晚餐指定配送日。  
   - **「自动划区」**：与「配送片区」标签 **同一行右侧**（`okfood-mem-edit-lab-row`）；标签与「自动划区」文案 **同字号**（0.6875rem / 700 / uppercase）。  
   - 片区下拉占满本列宽度。  
   - 晚餐长说明：桌面 `okfood-mem-edit-dinner-hint--desk`；小屏隐藏，标签旁 **ⓘ tooltip**（文案常量与正式一致）。  
3. **选项行**（`okfood-mem-edit-chk-band--one-row`）  
   - 顺序：**门店自提 → 暂停配送 → 暂停晚餐（若有）→ 周六不参与 → 强制加入当天配送大表**（按钮 `margin-left: auto`）。  
4. **备注**：`textarea` 默认 `minRows: 1`，`maxlength 500` + `show-word-limit`。

### 3.3 小屏紧凑（`max-height: 780px` 或 `max-width: 680px`）

- 隐藏弹窗 `subtitle`；收紧 head / 操作对象条 / body / foot padding。  
- 卡片间距与区内边距减小；配送网格改单列；选项行允许换行。  
- 仍依赖遮罩滚动，**不在 body 内嵌滚动条**。

---

## 4. 会员列表 / 列表容器

### 4.1 圆角与壳

- `--okfood-shell-radius: 14px`；`--okfood-surface-radius` 与其一致。  
- 会员表容器：`table-container--members-fill` **显式** `border-radius: var(--okfood-surface-radius)`，顶栏 `table-header--members` 白底 + 下投影、上圆角与壳一致（避免 flex 裁剪缺角）。

### 4.2 表体滚动

- 列表占满主区剩余高度：`members-view-fill` + `members-table-host`。  
- 表格类：`members-el-table-body-scroll` — **仅表体纵向滚动**，表头固定。

### 4.3 地址等列展示

- 地址过长：`members-address-cell-ellipsis` + `el-tooltip`（`members-address-tooltip-popper`），勿撑开行高。

---

## 5. 表头设计（el-table）

### 5.1 通用表（`admin-table--default`）

- 表头：深绿底 `var(--okfood-el-table-header-bg, #0e5a44)`，字色近白，**12px / 900 / uppercase / letter-spacing 2px**。  
- 表体：大行高 padding（与 legacy `.data-table` 对齐）。

### 5.2 会员档案表（`admin-table--members`）

- 在 default 基础上 **紧凑**：`el-table` **`size="small"`**。  
- 表头再压：`members-el-table-body-scroll` 下 header cell `padding: 0.3rem 0.55rem`，`.cell` **12px / 800 / line-height 1.2**。  
- 表体 cell：`padding: 0.38rem 0.65rem`，`border-bottom: #e2e8f0`。  
- 关键列 `min-width`：如手机号 `td-phone` ≥132px，避免 11 位截断。  
- 行 hover：`#fafafa`。

新会员列须评估是否折行撑高；优先 **列宽 + nowrap / ellipsis + tooltip**。

---

## 6. 其它会员弹窗（对齐同一壳）

| 弹窗 | size | fit | dlgClass | 要点 |
|------|------|-----|----------|------|
| 修改次数 | md | 否 | — | 剩余次数只读标签；仅改份数 |
| 送餐地址 | wide | 是 | `--addr-fit` | 列表 sticky + 地图有尺寸后再 mount |
| 手工请假 | md | 否 | — | 操作类型下拉在 body |
| 退卡 | wide | 是 | `--refund-fit` | 明细区独立滚动 |

新增会员操作弹窗：**必须** `OkfoodAdminDialogShell` + `MemberOperationContext`（除非纯系统级、无操作对象）。

---

## 7. 自检清单（提交前）

- [ ] 讨论稿与正式布局一致（或注明刻意差异）  
- [ ] 无 `window.confirm` 新用法  
- [ ] 弹窗挂 body、小屏无 body 双滚动  
- [ ] `edit-fit` / `addr-fit` 左右 14px，无错误居中窄栏  
- [ ] 改会员晚餐区符合 `showDinnerScheduleFor`  
- [ ] 表头/列表用 `admin-table--members` 紧凑规范，未破坏表体滚动  
- [ ] API 字段名未擅自改动（前后端 types 一致）

---

## 8. 文件索引

| 主题 | 路径 |
|------|------|
| 会员操作预览 | `design/okfood-admin-members-actions-preview.html` |
| 修改会员正式 | `src/views/components/MemberEditModal.vue` |
| 强制加入大表确认 | `src/composables/confirmForceReinstateDelivery.js` |
| MessageBox 皮肤 | `src/assets/okfood-el-glass-messagebox.css` |
| 全局弹窗样式 | `src/assets/admin-ui.css`（检索 `okfood-admin-dlg`） |
| 会员列表 | `src/views/MembersView.vue` |
