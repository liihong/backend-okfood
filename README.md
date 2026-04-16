# 会员登记与配送管理 API

技术栈：FastAPI + MySQL（同步 SQLAlchemy）+ 高德地理编码 + APScheduler + **真实短信通道**（阿里云或自建 Webhook）。

## 快速开始

1. 创建数据库并执行 [sql/schema.sql](sql/schema.sql)。若库已建过但**没有** `menu_dish` 等菜品表，可只执行 [sql/migration_011_menu_catalog_baseline.sql](sql/migration_011_menu_catalog_baseline.sql) 补齐；其余按需补跑 [sql/migration_007_menu_dish_schedule.sql](sql/migration_007_menu_dish_schedule.sql)（从旧 `daily_menu` 迁移时）、[sql/migration_009_menu_dish_image_url_text.sql](sql/migration_009_menu_dish_image_url_text.sql)（仅当 `image_url` 仍为 VARCHAR 需改为 TEXT）等。
2. 复制 `.env.example` 为 `.env`，填写 **MySQL 分项**（`MYSQL_HOST`、`MYSQL_USER`、`MYSQL_PASSWORD` 等，**不要写 JDBC/URL 连接串**）、`JWT_SECRET`、短信与 `AMAP_KEY`（高德 Web 服务）等。
3. 安装依赖：`pip install -r requirements.txt`
4. 初始化账号：
   - `python scripts/create_admin.py admin 你的密码`
   - `python scripts/create_courier.py C001 123456 张三`
5. 启动：`uvicorn app.main:app --reload --host 0.0.0.0 --port 8001`

## 短信（必配其一）

- **`SMS_PROVIDER=webhook`**：向 `SMS_WEBHOOK_URL` 发送 `POST`，JSON 为 `{"phone":"...","code":"..."}`，可选请求头 `Authorization: Bearer <SMS_WEBHOOK_TOKEN>`。由你的网关转发到任意短信服务商。
- **`SMS_PROVIDER=aliyun`**：配置 `ALIYUN_ACCESS_KEY_ID`、`ALIYUN_ACCESS_KEY_SECRET`、`ALIYUN_SMS_SIGN_NAME`、`ALIYUN_SMS_TEMPLATE_CODE`；模板内需包含变量 `code`。

验证码落库表 `sms_verification`，多实例一致；**接口响应中不会返回验证码**。

## 主要接口前缀

- 会员：`/api/user/*`（除 `register`/`sms/send` 外需会员 JWT）
- 菜单：`/api/menu/tomorrow`、`/api/menu/weekly`、`/api/menu/detail/{dish_id}`
- 配送：`/api/courier/*`（除 `login` 外需配送员 JWT）
- 管理：`/api/admin/*`（除 `login` 外需管理员 JWT）

会员登录：`POST /api/user/sms/send` → `POST /api/user/sms/login`。

## 前端联调

- 详见 [docs/前端接口联调说明.md](docs/前端接口联调说明.md)；启动后也可打开 **`/docs`**（Swagger）。

## 生产部署（ECS / Nginx / 宝塔 / 子域名）

- **分步操作流程与验收清单**：[docs/生产部署与域名说明.md](docs/生产部署与域名说明.md)
- Nginx 示例：[deploy/nginx-ok.sourcefire.cn.example.conf](deploy/nginx-ok.sourcefire.cn.example.conf)

## 说明

- 业务日与定时任务时区均为 **Asia/Shanghai**；验证码过期时间使用 **UTC** 存入 `sms_verification.expire_at`。
- 多实例部署时请避免重复执行 APScheduler，或改为独立 Worker。
- 密码中含 `@`、`:` 等字符时，使用分项 MySQL 配置即可，无需手工转义。
