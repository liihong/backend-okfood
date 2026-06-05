# OK Fine · 健康餐配送平台（后端 Monorepo）

面向 **OK Fine** 健康餐业务的 **会员订阅配送 + 单次点餐 + 开卡工单 + 顺丰同城履约** 一体化系统。本仓库以 **FastAPI 后端** 为核心，同目录包含 **Web 管理端** 与 **微信小程序** 前端工程。

| 子项目 | 路径 | 说明 |
|--------|------|------|
| 后端 API | 仓库根目录 `app/` | FastAPI + MySQL + APScheduler |
| 管理端 | [okfood-admin/](okfood-admin/) | Vue 3 + Vite，对接 `/api/admin/*` |
| 小程序 | [okfood-miniprogram/](okfood-miniprogram/) | uni-app 3，对接 `/api/user/*` 等 |

---

## 技术栈

- **Web 框架**：FastAPI、Uvicorn
- **数据库**：MySQL 8.0+、SQLAlchemy 2.x（同步）
- **鉴权**：JWT（会员 / 配送员 / 管理员分角色）
- **定时任务**：APScheduler（时区 `Asia/Shanghai`）
- **第三方**：微信小程序登录、微信支付 v2（JSAPI）、高德地理编码、顺丰同城开放平台、阿里云 OSS（可选）
- **限流**：slowapi（按 IP，登录类接口）

---

## 业务能力概览

### 会员（小程序 `/api/user/*`）

- 微信小程序手机号一键登录（`js_code` + `phone_code`），写入 `members.wx_mini_openid`
- 会员档案、多地址、配送片区校验（高德 GCJ-02 + 多边形匹配）
- 请假（明日 / 区间）、激活计划、扣次记录查询
- **开卡工单**与 **单次点餐**下单，支持微信支付 JSAPI 与异步回调
- 头像上传（本地 `UPLOAD_DIR` 或 OSS）
- 订阅消息：送达通知、低余额续费提醒

### 菜单（公开 `/api/menu/*`）

- 明日菜单、周菜单、菜品详情
- 管理端维护菜品库、周槽位排期、日总份库存

### 配送员（`/api/courier/*`）

- 工号 / 手机号登录
- 当日任务列表、确认送达（按 `daily_meal_units` 扣次，累计配送费）

### 管理端（`/api/admin/*` 及子路由）

- **营业概览**、**智能配送大表**、配送标记
- 会员档案、开卡工单、订单管理（单次点餐 / 商城卡包）
- 菜品 / 本周菜单、配送区域与地图、配送员、门店配置
- 财务实收汇总、系统通知
- **顺丰推单**：预览、批量推送、监控、重试、取消、履约同步
- 单次订单派单：顺丰零售 / UU / 门店骑手；微信退款
- **多租户平台**（`/api/admin/system/*`）：租户、门店、管理员、对接配置
- **商品目录**（`/api/admin/catalog/*`）：会员卡模板、零售分类与 SKU

### 回调（无 JWT）

- 微信支付：`POST /api/pay/wechat/notify`
- 顺丰同城：`/api/sf/callback/*`、`/api/sf/oauth/*`（验签）
- 抖音团购 SPI：`POST /api/douyin/spi/async-cancel-fulfil`（撤销核销异步回调，验签）
- 抖音 Webhooks：`POST /api/douyin/webhook`（平台事件订阅；保存 URL 时回显 challenge）

### 多门店

- 公开与会员接口可通过请求头 **`X-Store-Id`** 指定门店；未传时默认 `DEFAULT_STORE_ID`（通常为 1）
- 会员 JWT 与档案 `store_id` 须一致
- 管理员按所属租户隔离数据；平台管理员可管理租户

---

## 快速开始（后端）

**环境要求**：Python 3.11+（推荐）、MySQL 8.0+

### 1. 数据库

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS meal_delivery DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p meal_delivery < sql/schema.sql
```

- 新库直接导入 [`sql/schema.sql`](sql/schema.sql) 即可（已合并历史迁移说明于文件头注释）。
- 若库较旧、缺少 **`admin_dashboard_biz_day_snapshots`** 等表，按需补跑 [`sql/migration_030_admin_dashboard_biz_day_snapshots.sql`](sql/migration_030_admin_dashboard_biz_day_snapshots.sql)。

### 2. 环境变量

```bash
cp .env.example .env
```

填写 **MySQL 分项**（`MYSQL_HOST`、`MYSQL_USER`、`MYSQL_PASSWORD` 等，**不要写 JDBC/URL 连接串**）、`JWT_SECRET`、`WX_MINI_APPID` / `WX_MINI_SECRET`、`AMAP_KEY` 等。完整项见 [`.env.example`](.env.example)。

生产环境 `DEBUG=false` 时，`JWT_SECRET` 禁止使用默认值且长度须 ≥ 16。

### 3. 依赖与账号

```bash
pip install -r requirements.txt

# 完整后台管理员（默认租户 1）
python scripts/create_admin.py admin 你的密码

# 可选：配送-only / 客服 / 平台管理员
python scripts/create_admin.py ops_user secret --role delivery
python scripts/create_admin.py platform secret --role system

python scripts/create_courier.py C001 123456 张三
```

### 4. 启动

**API 服务**（默认端口 **8001**，与常见 8000 服务错开）：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**定时任务**（生产必须与 API 分离；本地开发可设 `ENABLE_IN_PROCESS_SCHEDULER=true` 嵌入 API 进程）：

```bash
python -m app.jobs.worker
```

| 任务 | 时间（上海） | 说明 |
|------|--------------|------|
| 请假标记重置 | 每日 00:01 | 清理过期「明日请假」与长期请假区间 |
| 低余额扫描 | 每日 18:00 | 兜底扫描（主路径为扣次后订阅消息） |
| 顺丰自动推单 | 每日 08:50 | 对已启用自动推单的门店推送当日配送大表 |

### 5. 验证

- 健康检查：`GET /health`（无需 `/api` 前缀）
- 在线文档：`/docs`（Swagger）、`/redoc`
- 冒烟测试：`pytest`（无需真实 MySQL）；新用户卡包购卡回调链路：`pytest tests/test_miniprogram_new_user_card_flow.py -v`
- 配送资质核验：`scripts/curl_delivery_region_consult.sh`（`POST /api/admin/delivery-region/consult`）

---

## API 约定

- **前缀**：业务接口统一 **`/api`**
- **成功响应**：`{ "code": 200, "data": ..., "msg": "..." }`
- **失败响应**：`{ "code": <HTTP状态码>, "data": null, "msg": "..." }`
- **鉴权**：`Authorization: Bearer <token>`（登录接口在 `data.access_token` 返回）

### 主要路由前缀

| 前缀 | 鉴权 | 说明 |
|------|------|------|
| `/api/user/*` | 会员 JWT（`register`、`wx/mini/login` 等除外） | 小程序会员端 |
| `/api/menu/*` | 无 | 菜单查询 |
| `/api/courier/*` | 配送员 JWT（`login` 除外） | 骑手端 |
| `/api/admin/*` | 管理员 JWT（`login` 除外） | 管理端主接口 |
| `/api/admin/catalog/*` | 管理员 JWT | 会员卡模板、零售商品 |
| `/api/admin/system/*` | 平台管理员 | 租户 / 门店 / 对接配置 |
| `/api/pay/wechat/*` | 无（微信服务器回调） | 支付通知 |
| `/api/sf/*` | 无（顺丰验签） | 同城回调与 OAuth |

接口字段与示例详见 [docs/前端接口联调说明.md](docs/前端接口联调说明.md)。

---

## 前端工程

### 管理端（okfood-admin）

```bash
cd okfood-admin
npm install
npm run dev    # 默认 http://localhost:5173，/api 代理到后端
```

详见 [okfood-admin/README.md](okfood-admin/README.md)。开发时在 `.env.local` 配置 `VITE_PROXY_TARGET` 与高德 `VITE_AMAP_KEY`。

### 微信小程序（okfood-miniprogram）

```bash
cd okfood-miniprogram
npm install
npm run dev:mp-weixin
```

用微信开发者工具打开 `dist/dev/mp-weixin`。API 根地址在 `src/utils/api.js` 的 `API_BASE`。详见 [okfood-miniprogram/README.md](okfood-miniprogram/README.md)。

---

## 生产部署

- **登录服务器后如何操作**：[deploy/README.md](deploy/README.md)
- **分步流程与验收**：[docs/生产部署与域名说明.md](docs/生产部署与域名说明.md)
- **增量更新脚本**：[deploy/update-production.sh](deploy/update-production.sh)
- **Nginx 示例**：[deploy/nginx-ok.sourcefire.cn.example.conf](deploy/nginx-ok.sourcefire.cn.example.conf)
- **API systemd 示例**：[deploy/okfine-api.service.example](deploy/okfine-api.service.example)
- **Scheduler systemd 示例**：[deploy/okfine-scheduler.service.example](deploy/okfine-scheduler.service.example)

推荐架构：

- **API**：`okfine-api`（Uvicorn，本机 8001，Nginx 反代 HTTPS）
- **Scheduler**：`okfine-scheduler`（`python -m app.jobs.worker`）
- **管理端静态资源**：`okfood-admin/dist`，由 Nginx 单独 `root` 或子路径托管

---

## 项目结构（后端）

```
app/
├── api/           # 路由层（user / admin / courier / menu / wechat_pay / sf_open_notify …）
├── core/          # 配置、鉴权依赖、门店作用域、限流
├── db/            # SQLAlchemy Session
├── integrations/  # 微信支付等外部封装
├── jobs/          # APScheduler 任务与独立 worker
├── models/        # ORM 模型
├── schemas/       # Pydantic 入参/出参
├── services/      # 业务逻辑
└── main.py        # FastAPI 入口、CORS、静态文件 /static
scripts/           # 初始化管理员、配送员、数据回填等 CLI
sql/               # schema.sql 与增量 migration
tests/             # pytest 冒烟
deploy/            # 生产脚本与 Nginx / systemd 示例
docs/              # 联调与部署文档
```

---

## 说明

- **业务日与时区**：均为 **Asia/Shanghai**（含请假、配送大表、定时任务）。
- **多实例 API**：进程内限流为单机内存计数；多副本请在网关层叠加限流。定时任务仅运行 **一个** scheduler worker，勿多开。
- **进程内调度器**：`.env` 中 `ENABLE_IN_PROCESS_SCHEDULER=false`（默认）；生产务必 false 并使用独立 worker。
- **MySQL 密码**：含 `@`、`:` 等特殊字符时使用分项配置即可，无需手工转义。
- **静态资源**：本地上传目录挂载为 `/static`；配置 `BASE_URL` 后写入库的 `image_url` 为绝对地址。
- **顺丰 / 微信支付**：密钥、回调 URL、小程序 AppID 与商户号绑定关系见 `.env.example` 注释；回调须 HTTPS 且公网可达。
