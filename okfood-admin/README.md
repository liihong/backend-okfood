# OK Fine · 超级管家后台（okfood-admin）

面向 **OK Fine** 健康餐业务的 **Web 管理端** 单页应用：森林绿品牌视觉、侧边导航多模块工作台，**对接后端 `POST /api/admin/login` 及各类 `/api/admin/*` 接口**进行真实数据管理（会员、配送区域、配送员、财务占位等）。

---

## 技术栈

| 类别 | 选用 |
|------|------|
| 框架 | [Vue 3](https://vuejs.org/)（Composition API + `<script setup>`） |
| 构建 | [Vite](https://vitejs.dev/) 8.x |
| 图标 | [lucide-vue-next](https://lucide.dev/) |

---

## 功能模块（侧边栏）

- **营业概览**：指标卡片占位，待对接统计接口后赋值  
- **会员档案**：`GET /api/admin/users` 分页与检索  
- **配送大表**：占位列表，待对接订单/线路聚合接口  
- **配送区域**：`GET/POST/PATCH/DELETE /api/admin/delivery-regions`，地图需配置高德 `VITE_AMAP_KEY`（及建议的 `VITE_AMAP_SECURITY_CODE`）  
- **配送员管理**：`/api/admin/couriers` 等  
- **财务中心**：金额与流水占位，待对接财务接口  
- **餐谱管理**：本地列表编辑 UI；与后端 `POST /api/admin/menu` 的联调可按需接入  

顶部 **极速开单**：需后端提供管理员创建会员等接口后再对接；提交时会提示当前未接 API。

---

## 本地开发

**环境要求：** Node.js 18+（推荐 LTS）

```bash
cd okfood-admin
npm install
npm run dev
```

浏览器访问终端里提示的本地地址（一般为 `http://localhost:5173`）。

**环境变量：** 复制 `.env.example` 为 `.env.local`。开发时通过 `VITE_PROXY_TARGET` 将 `/api` 代理到本地或远程后端（须挂载 `/api` 路径）。生产构建可设置 `VITE_API_BASE_URL` 为完整 API 根地址。

**登录：** 使用数据库中配置的管理员账号密码调用后端登录接口。可选在 `.env.local` 中设置 `VITE_ADMIN_LOGIN_PRESET_USER` / `VITE_ADMIN_LOGIN_PRESET_PASSWORD` 仅用于本地预填输入框（勿提交真实密码）。

### 其他脚本

```bash
npm run build    # 生产构建，输出到 dist/
npm run preview  # 本地预览构建结果
```

---

## 项目结构（简要）

```
okfood-admin/
├── index.html
├── package.json
├── vite.config.js
├── public/           # 静态资源（如 favicon）
└── src/
    ├── main.js       # 入口
    ├── App.vue       # 主布局与业务页面（单文件体量较大）
    └── style.css     # 全局样式
```

---

## 上传到 GitHub 时注意

- 仓库中 **不要提交** `node_modules/`、`dist/`（本仓库 `.gitignore` 已忽略）。  
- 首次克隆后需在项目根目录执行 `npm install` 再开发或构建。  

---

## 许可证

私有项目或未声明许可证时，默认 **保留所有权利**；若需开源，请自行补充 `LICENSE` 文件。
