# OK 饭 · 微信小程序

基于 **uni-app3**（Vue 3 + Vite）的微信小程序端，与后端 `https://ok.sourcefire.cn` 对接（接口路径以 `/api/...` 开头）。

## 环境要求

- **Node.js**：建议 18 LTS 或以上（与 Vite 5 兼容）
- **微信开发者工具**：用于导入编译产物、真机预览与上传

## 安装与运行

```bash
cd okfood-miniprogram
npm install
```

### 开发（微信小程序）

```bash
npm run dev:mp-weixin
```

编译输出目录默认为 **`dist/dev/mp-weixin`**。用微信开发者工具打开该目录（或项目内配置的输出路径），在「详情 → 本地设置」中按需勾选「不校验合法域名」等（开发阶段 `manifest.json` 里已设置 `urlCheck: false`）。

### 生产构建

```bash
npm run build:mp-weixin
```

产物在 **`dist/build/mp-weixin`**，用于上传体验版/正式版。

### 其他端（可选）

仓库内同样配置了 H5、支付宝等脚本，例如：`npm run dev:h5`、`npm run build:h5`。主目标为微信小程序。

## 项目结构（简要）

| 路径 | 说明 |
|------|------|
| `src/pages/` | 主包页面：菜单（排餐）、我的、骑手 Tab（`pages/courier/*` 工作台与配送单） |
| `src/packageOrder/` | 订单分包：餐品详情等 |
| `src/packageUser/` | 用户分包：请假、地址列表/编辑等 |
| `src/packageRider/` | 骑手分包：登录、个人中心（须在分包内；Tab 页不可放在此 root 下） |
| `src/utils/` | 请求封装 `api.js`、菜单接口 `menuApi.js`、登录等 |
| `src/components/` | 公共组件（如导航栏） |
| `src/pages.json` | 页面路由、分包、`tabBar` |
| `src/manifest.json` | 应用名称、版本、各端 AppID 等 |

底部 **Tab**：「菜单」与「我的」。

## 配置说明

### 微信小程序 AppID

在 **`src/manifest.json`** → `mp-weixin.appid` 中配置。更换主体或小程序时需同步修改，并在微信后台配置服务器域名（request 合法域名需包含 API 主机）。

### API 根地址

在 **`src/utils/api.js`** 中修改常量 **`API_BASE`**（无末尾 `/`）。所有请求会拼接为 `{API_BASE}/api/...`。

会员态 Token 使用本地存储键 **`okfood_member_token`**（见同文件）。

## 与后端约定（前端侧）

- 周菜单、详情等接口由 `src/utils/menuApi.js` 映射字段；列表项对外主要使用 **`dishId`**，页面跳转参数为 **`dish_id`**（仍兼容历史 `food_id` / `foodId`解析）。
- 具体路径以 `api.js` 与各业务模块中的 `request('/api/...')` 为准。

## 常见问题

- **白屏或接口失败**：检查开发者工具是否关闭域名校验（仅开发）、以及正式环境是否已在公众平台配置 request 合法域名。
- **改代码不生效**：确认微信开发者工具打开的是当前构建输出目录，并尝试重新编译或清除缓存。

## 技术栈

- Vue 3、uni-app 3、Vite 5、Sass

---

如有 H5 或其它仓库，与本项目并列在 monorepo 的 `app` 目录下时，小程序仅负责本目录依赖与构建，不与 H5 共用 `node_modules`。
