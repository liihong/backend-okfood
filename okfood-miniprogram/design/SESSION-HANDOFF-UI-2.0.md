# 小程序 UI 2.0 · 会话交接

> 写于 2026-11-11，办公室这台 Cursor。家里拉下代码后，让 Cursor **先读本文件**，再继续。  
> 本文件只交接结论，不改业务代码。

## 给下一个 Cursor

用户要开始做 **小程序 UI 2.0**，范围是 **只改界面**，不动接口、字段和业务逻辑。

接着做的第一件事：按管理端现有文档的写法，起草一份小程序视觉说明（建议放在 `okfood-miniprogram/design/`），给用户看过再改 Vue。不要一上来改页面。

回复用简体中文。注释用中文。能复用的样式不要在每个页面里再抄一份。

## 已经对齐的结论

1. 管理端 2.0 的界面改得差不多了。小程序是下一件，同样只改 UI。
2. 工作量比管理端小一档。
   - 换皮（布局不动，换颜色、圆角、间距、按钮、卡片、导航和 Tab）：用户端大约 **8–12 个工作日**。
   - 连版式一起重排：大约 **3–4 周**。
   - 配送员 / 骑手 6 页另算，大约再加 **2–3 天**，默认先不动。
3. 现有规范 **只能借用气质，不能把页面规范套过来**。
4. 视觉目标是现在的 **iOS Liquid Glass**（iOS 26 人机界面指南），不是把后台的侧栏、表格、弹窗搬进小程序。

## 规范怎么用

| 文档 | 小程序 |
|---|---|
| `okfood-admin/design/VISUAL-DIRECTION-IOS-GLASS.md` | 用。空气感底、材质分级、圆角两档（16 / 22–24）、单层轻阴影、8px 间距、玻璃上的字用深色实色 |
| `okfood-admin/design/COLOR-PRIMARY-CANDIDATES.md` | 用。默认蜜桃珊瑚 `#E8927C`，备选莫吉托 `#5CBF8E`、雾紫 `#8B7EC8`。主色只给按钮、选中和关键描边 |
| `okfood-admin/design/IOS-GLASS-IMPLEMENTATION.md` 第 4 节 | 只借用「玻璃少、密集内容用实底」 |
| `okfood-admin/design/ADMIN-UI-DIALOG-LIST-SPEC.md` | 不用。那是 Element Plus 的表头、会员弹窗、抽屉和侧栏 |

小程序壳层按这几条，不要按后台顶栏来：

- 导航：滚动后才出现一层薄玻璃，正文区保持实色。
- Tab：悬浮胶囊，贴在安全区上方；选中项是实色胶囊，不要现在这种贴底白条。
- 按钮：主操作用胶囊填充，次操作用浅底或细边。
- 圆角：外层卡片和内层控件同心，内圆角约等于外圆角减去内边距。
- 玻璃只放三处：导航、Tab、首页那一张主卡。菜单、确认页、地址表单用白底或极浅实底。

微信里没有系统 Liquid Glass。`backdrop-filter` 在 iOS 微信上勉强能用，安卓经常没有折射还会掉帧。玻璃做成高不透明度的薄层，并准备一层实色回退。

## 代码事实（2026-11-11）

- 小程序在 `okfood-miniprogram/`，uni-app Vue。
- 56 个 Vue，约 2.1 万行，其中样式约 8900 行。样式几乎都在各页 `<style>` 里。
- 公共变量只有 `okfood-miniprogram/src/uni.scss`，品牌绿 `#73B054`。没有管理端那种一套 `admin-ui.css`。
- 用户能走到的页面大约 26 个：4 个 Tab（首页、点单、订单、我的）+ `packageOrder` + `packageUser`。路由在 `okfood-miniprogram/src/pages.json`。
- 最大的几页：`src/pages/mine/index.vue`（1757 行）、`src/packageOrder/pages/singleConfirm/singleConfirm.vue`（1241 行）、`src/packageOrder/pages/retailConfirm/retailConfirm.vue`（1192 行）。
- 自定义导航 `src/components/OkNavbar/OkNavbar.vue`，Tab 在 `pages.json` 里是 `custom: true`。
- 配送员 `src/pages/courier/`、骑手 `src/pages/rider/` 先不要改。

建议改的顺序：先写视觉说明 → 公共壳（导航、Tab、按钮、卡片、弹层）→ 四个 Tab → 下单链路 → 账户链路（地址、请假、卡包、券、抖音核销）。

## 不要做

- 不要改 API 字段，不要改下单、支付、地址、券的业务逻辑。
- 不要把 `ADMIN-UI-DIALOG-LIST-SPEC.md` 的表格和弹窗结构套进小程序。
- 不要整页铺 `backdrop-filter`。
- 不要先改配送员 / 骑手页。
- 管理端 `.cursorrules` 里的 Element Plus、`ElMessageBox`、`showToast` 只约束 `okfood-admin/**`，不要搬进小程序。

## 办公室这台机器上的其他改动

本交接提交 **只含本文件**。管理端还有一批未提交改动（样式、列表、预览稿删除等），不在这次提交里。家里 `git pull` 看不到那些管理端改动。
