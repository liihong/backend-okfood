# OK 轻食管理端 · 列表 / 弹窗 / 表头设计规范

> **状态**：会员弹窗 / 列表，以及 2026-11-11 定下的页面级版式，都以本文为硬规范。  
> **真源 CSS**：`src/assets/admin-ui.css`（弹窗壳、`okfood-mem-edit-*`、`admin-table--members`、顺丰核对弹窗等）  
> **真源组件**：`src/components/OkfoodAdminDialogShell.vue`、`MemberOperationContext.vue`、`src/components/StatRollNumber.vue`  
> **色与壳层**：`VISUAL-DIRECTION-IOS-GLASS.md`、`IOS-GLASS-IMPLEMENTATION.md`、`COLOR-PRIMARY-CANDIDATES.md`

与 iOS 玻璃稿的关系：**壳层氛围、主色三套以玻璃稿为准；弹窗、列表和下面第 9 节的页面版式以本文为硬规范。** 已落地页面不再往 `design/` 堆预览 HTML、截图和裁切图。

---

## 1. 工作流

1. 先对齐本文（弹窗 §2–3、列表 §4–5、页面版式 §9）和玻璃色板，再改 Vue。  
2. 业务逻辑 / 接口字段 **不重写**；只换壳、间距和 `admin-ui.css` 类名。  
3. 样式 **优先写入 `admin-ui.css`**，组件内 `scoped` 仅补局部；禁止再新增整页 `modal-overlay` + 深绿顶栏。  
4. 设计语言已经定过的页面（财务、会员统计、配送、顺丰、菜单、商品、骑手等）**直接改正式代码**，不要再新建 `design/*-preview.html`。  
5. 结构还没定的新页面可以临时出一版静态预览给确认；确认并落地后，把约束写回本文，预览、截图、裁切图删掉。

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
| 修改次数 | md | 否 | — | 可改午/晚实际剩余次数（立即覆盖）与每配送日份数 |
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
| 修改会员正式 | `src/views/components/MemberEditModal.vue` |
| 强制加入大表确认 | `src/composables/confirmForceReinstateDelivery.js` |
| MessageBox 皮肤 | `src/assets/okfood-el-glass-messagebox.css` |
| 全局弹窗样式 | `src/assets/admin-ui.css`（检索 `okfood-admin-dlg`） |
| 会员列表 | `src/views/MembersView.vue` |
| 数字滚动 | `src/components/StatRollNumber.vue` |
| 财务 / 会员统计 | `src/views/FinanceView.vue`、`src/views/MemberStatsView.vue` |
| 配送 / 顺丰核对 | `src/views/DeliveryView.vue`（`okfood-admin-dlg--sf-push`） |
| 顺丰订单 | `src/views/SfOrdersMonitorView.vue` |
| 后厨看板（未进 Vue，预览先留） | `design/okfood-admin-kitchen-board-preview.html` |

---

## 9. 页面级版式（2026-11-11）

今天按同一套 OpenDesign（iOS 毛玻璃 + 蜜桃珊瑚默认，可切莫吉托 / 雾紫）改过的页面，以后都按下面做。改样式时不改接口字段。

### 9.1 整页

- 列表页撑满主区，底边和左侧菜单对齐。数据多时 **只滚列表**，页头、工具条、底部分页固定，整页不要跟着滚。
- 同一行左右两张卡片 **等高**。右边卡片底部收紧，上下看起来匀称，不要一边高出一截。
- 小屏内容不要被挤出视口。筛选项、状态胶囊多的时候，**一排，最多两排，多出来横向滚动**，不要把页面撑出底部横向滚动条。
- 标题、价格、日期、汇总数字，一行写得下就不要折行。
- 少写解释性长文案。执行的人要一眼看到自己在看什么。状态用标签（如热 / 冷 / 够），不要堆成段落。

### 9.2 数字

- 关键数字用 `StatRollNumber` 滚动。keep-alive 切回页面时可以重播。
- 数字和单位同一基线。`4` 和 `户` 在同一行，数字不要掉下去。
- 同一排的笔数、金额、份数按列对齐。
- 重点数字放大，并带上颜色。切换蜜桃 / 莫吉托 / 雾紫时，这些颜色仍然要看得清。
- 日期操作放进对应卡片里：上一日 / 下一日在日净收入卡内，月份选择在月净收入卡内。不要另起一条「不随日期切换」的说明。

### 9.3 表格与筛选

- 表头 hover **不变色**。
- 复选框选中态要完整，不要出现选中后样式残缺。
- 全选用已经定过的紧凑样式，不要再堆一块「全选」把左右卡片撑得不等高。
- 时间筛选放在页头指定位置，不放进滚动列表。
- 汇总数字和明细同一排。例如总数后面直接跟自提单、配送点，并把各自数量标出来。
- 下方配送列表固定。上下滚动时表头和汇总不要跟着乱。
- 长说明列给短列让位，避免整表被撑出一条用不到的横向滚动条。

### 9.4 抽屉与图片

- 新建、编辑商品从 **右侧抽屉** 打开，不跳到下一页。
- 抽屉里图片列加宽、表单列收窄。竖图按竖图展示，以看全为准。
- 菜品图、餐次图可以点开大图。
- 搜索框、分类、主按钮在同一行，高度一致。数量（如「共 90 道菜」）做重点，不要和筛选项上下叠成两行。

### 9.5 本周菜单

- 左右切换菜单的按钮不能被挡住。
- 「日总份数」输入框收小。单点价一行展示。
- 周期名称只写「本周菜单」「下周菜单」。
- 日期只写「11月9日 - 11月15日」这种，不写「起」「止」，并且和标题一排。
- 午餐菜单配置那一排同样带这段日期。
- 「应配送多少份」「损耗」在这个页面没有业务作用，不展示。

### 9.6 顺丰核对弹窗

- 宽表弹窗用 `okfood-admin-dlg--sf-push`。
- 一屏之内 **只滚表格**，标题和底栏留在外面。
- 标记送达要有看得见的状态，不要只改数据不改样子。

### 9.7 后厨看板（还没进 Vue）

给厨师、帮厨、打包看的大屏，不是操作台。电视上要一页看全，笔记本上也要能看全。时钟实时走。风格仍是 iOS 毛玻璃，但每个模块要有分量，不要一片玻璃上写几个字。

同一页分成这些模块：

1. **配餐图例**：餐图竖着、放大。名称和辣度放在「日期 + 周几 + 午餐/晚餐」下面。右边居中写出今日出餐、配送、自提、零售，以及销售量和剩余量。
2. **餐次原材料**：这一餐里有哪些料。不显示留样。净重只用来判断大概放几个，不要把每种料的克数说明铺满屏幕。
3. **装配成品**：第一步到第四步放什么。顺序给依据即可，不写死「必须米饭打底」——有的餐是意面、红薯或紫薯。
4. **随餐饮**：单独一块，写用什么瓶子装。
5. **耗材用量**：盒型（如 900 盒）和打包耗材。

后厨和打包 **只看总出餐量**。临时可售是销售的事，不放在这块板上。配菜到 10 个时在模块里收紧或内部滚动，不要撑破大屏。特殊餐、赠品写在备注里，没有固定字段，不要为此单做一步。装勺子、筷子不是装配流水线的一步。

预览先留在 `design/okfood-admin-kitchen-board-preview.html`。进 Vue 之后按 §1 把预览删掉。

### 9.8 自检

- [ ] 只滚该滚的那一块，页头和分页不动
- [ ] 左右卡片等高，小屏没有被挤出屏幕，也没有多余的横向滚动条
- [ ] 重点数字用 `StatRollNumber`，数字和单位同一基线，同一排对齐
- [ ] 日期切换在对应卡片内部
- [ ] 表头 hover 不变色，复选框选中态完整
- [ ] 新建商品是右侧抽屉，图片可点开大图
- [ ] 没有为了改样式再往 `design/` 加预览 HTML 或截图
