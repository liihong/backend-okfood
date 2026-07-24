# 生产部署操作说明

本文说明 **登录远程服务器之后** 如何部署、更新与排障。域名与路径一览见 [docs/生产部署与域名说明.md](../docs/生产部署与域名说明.md)。

## 本目录文件

| 文件 | 用途 |
|------|------|
| [update-production.sh](update-production.sh) | **日常增量更新**（拉代码、装依赖、重启服务） |
| [okfine-api.service.example](okfine-api.service.example) | API 的 systemd 单元示例 |
| [okfine-scheduler.service.example](okfine-scheduler.service.example) | 定时任务 worker 的 systemd 单元示例 |
| [nginx-ok.sourcefire.cn.example.conf](nginx-ok.sourcefire.cn.example.conf) | Nginx 配置参考（新环境） |
| 线上 Nginx 实录 | [docs/ok.source.cn.conf](../docs/ok.source.cn.conf)（含 `/admin`） |

## 生产环境约定

| 项 | 路径 / 名称 |
|----|-------------|
| 后端代码 | `/var/www/okfood/backend` |
| Python 虚拟环境 | `/var/www/okfood/backend/.venv` |
| 环境变量 | `/var/www/okfood/backend/.env` |
| H5 静态 | `/var/www/okfood/h5`（Nginx 根路径 `/`） |
| 管理端静态 | `/var/www/okfood/backend/okfood-admin/dist`（路径 `/admin`） |
| API 进程 | systemd **`okfine-api`**，监听 `127.0.0.1:8001` |
| 定时任务 | systemd **`okfine-scheduler`**，`python -m app.jobs.worker` |
| 对外域名 | `https://ok.sourcefire.cn` |

---

## 一、登录服务器后：日常更新（最常用）

代码已推送到 Git 远程后，SSH 登录服务器执行：

```bash
bash /var/www/okfood/backend/deploy/update-production.sh
```

脚本会自动：

1. 在 `/var/www/okfood/backend` 执行 `git pull --ff-only`（可用环境变量跳过，见下）
2. 用 `.venv` 安装/更新 `requirements.txt`
3. `systemctl restart okfine-api`（及已安装的 `okfine-scheduler`）
4. 本机 `curl http://127.0.0.1:8001/health` 做快速检查

当前用户若无 `systemctl` 权限，脚本会自动加 `sudo`；也可直接：

```bash
sudo bash /var/www/okfood/backend/deploy/update-production.sh
```

### 可选环境变量

```bash
# 顺带在服务器构建管理端（需已安装 Node.js / npm）
BUILD_ADMIN=1 bash /var/www/okfood/backend/deploy/update-production.sh

# 不拉 Git（例如仅改了 .env 或手动 rsync 过代码）
SKIP_GIT=1 bash /var/www/okfood/backend/deploy/update-production.sh

# 自定义路径（非默认目录时）
BACKEND_ROOT=/var/www/okfood/backend bash /var/www/okfood/backend/deploy/update-production.sh
```

### 更新后验收

```bash
curl -s https://ok.sourcefire.cn/health
# 期望: {"status":"ok"}

curl -s http://127.0.0.1:8001/health
```

浏览器可访问：`https://ok.sourcefire.cn/admin`（管理端）、`https://ok.sourcefire.cn/`（H5）。

---

## 二、登录服务器后：常用运维命令

### 查看服务状态

```bash
sudo systemctl status okfine-api
sudo systemctl status okfine-scheduler
sudo systemctl status nginx
```

### 重启服务

```bash
# 仅重启 API（改 .env 后必做）
sudo systemctl restart okfine-api

# 仅重启定时任务
sudo systemctl restart okfine-scheduler

# 改 Nginx 配置后
sudo nginx -t && sudo systemctl reload nginx
```

### 启动微信第三方 platform verify_ticket 推送

控制台显示「关闭推送 Ticket」时，**须在服务器白名单 IP 上**执行（勿在本机调，会报 61004）：

```bash
cd /var/www/okfood/backend
bash scripts/start_wx_component_push_ticket.sh
```

或管理后台 **租户管理 → 启动 Ticket 推送**（需已部署含该接口的后端）。

### 查看日志

```bash
journalctl -u okfine-api -f
journalctl -u okfine-scheduler -f
sudo tail -f /var/log/nginx/error.log
```

### 仅更新管理端前端

```bash
cd /var/www/okfood/backend/okfood-admin
npm ci && npm run build
# 产物在 dist/，Nginx 已指向该目录则无需重启 API
```

### 修改环境变量

```bash
sudo nano /var/www/okfood/backend/.env
sudo systemctl restart okfine-api
# 若 scheduler 也依赖该配置:
sudo systemctl restart okfine-scheduler
```

生产注意：`DEBUG=false`，`JWT_SECRET` 须为足够长的随机串；`CORS_ORIGINS` 须包含 `https://ok.sourcefire.cn`；`BASE_URL=https://ok.sourcefire.cn`（上传图片绝对地址）。完整项见仓库根目录 `.env.example`。

---

## 三、首次部署（新机器或重装）

以下在 **已安装** Ubuntu/Debian 系、Nginx、MySQL 8、Python 3.11+、Git 的前提下进行。若使用宝塔，Nginx/SSL 可在面板操作，后端仍按本节安装 systemd 服务。

### 1. 准备目录与代码

```bash
sudo mkdir -p /var/www/okfood
sudo chown -R $USER:$USER /var/www/okfood   # 或部署专用用户

cd /var/www/okfood
git clone <你的仓库地址> backend
cd backend
```

### 2. Python 虚拟环境与依赖

```bash
cd /var/www/okfood/backend
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```

### 3. 数据库

在 MySQL 中创建库并导入结构（本机或远程库均可，`.env` 里配置连接）：

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS meal_delivery DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p meal_delivery < /var/www/okfood/backend/sql/schema.sql
```

### 4. 环境变量

```bash
cp /var/www/okfood/backend/.env.example /var/www/okfood/backend/.env
nano /var/www/okfood/backend/.env
```

至少配置：`MYSQL_*`、`JWT_SECRET`、`CORS_ORIGINS`、`BASE_URL`，以及微信/高德等业务密钥。

### 5. 初始化管理员（首次）

```bash
cd /var/www/okfood/backend
.venv/bin/python scripts/create_admin.py admin '你的强密码'
```

### 6. 安装 systemd 服务

```bash
cd /var/www/okfood/backend

sudo cp deploy/okfine-api.service.example /etc/systemd/system/okfine-api.service
sudo cp deploy/okfine-scheduler.service.example /etc/systemd/system/okfine-scheduler.service

# 若代码不在 /var/www/okfood/backend，先编辑上述两个文件中的路径与用户
sudo nano /etc/systemd/system/okfine-api.service
sudo nano /etc/systemd/system/okfine-scheduler.service

# 确保 .env 与目录对 www-data 可读（示例服务以 www-data 运行）
sudo chown -R www-data:www-data /var/www/okfood/backend/.env
# 上传目录等也需 www-data 可写，按实际上传配置调整 UPLOAD_DIR 权限

sudo systemctl daemon-reload
sudo systemctl enable --now okfine-api okfine-scheduler
```

确认本机 API：

```bash
curl -s http://127.0.0.1:8001/health
```

`.env` 中 **`ENABLE_IN_PROCESS_SCHEDULER` 保持 `false`**（默认），定时任务只由 `okfine-scheduler` 运行，不要多开 worker。

### 7. 前端静态资源

**H5**（站点根 `/`）：

```bash
# 将构建好的 H5 放到（路径与 Nginx root 一致）
/var/www/okfood/h5
```

**管理端**（路径 `/admin`）：

```bash
cd /var/www/okfood/backend/okfood-admin
npm ci && npm run build
# 产物: okfood-admin/dist
```

### 8. Nginx 与 HTTPS

- 线上可参考：[docs/ok.source.cn.conf](../docs/ok.source.cn.conf)（单域名：`/` H5、`/admin` 管理端、`/api` 反代 8001）
- 新环境参考：[nginx-ok.sourcefire.cn.example.conf](nginx-ok.sourcefire.cn.example.conf)

```bash
# 示例：站点配置放到 sites-enabled 后
sudo nginx -t
sudo systemctl reload nginx

# Let's Encrypt（若未在宝塔申请）
sudo certbot --nginx -d ok.sourcefire.cn
```

### 9. 验收清单

- [ ] `curl http://127.0.0.1:8001/health` → `{"status":"ok"}`
- [ ] `curl https://ok.sourcefire.cn/health` → 同上
- [ ] `https://ok.sourcefire.cn/admin` 可打开并登录
- [ ] `systemctl is-active okfine-api okfine-scheduler` 均为 `active`

---

## 四、按场景操作速查

| 场景 | 登录后执行 |
|------|------------|
| 后端代码已 push，Routine 发布 | `bash .../deploy/update-production.sh` |
| 只改了 `.env` | 编辑 `.env` → `sudo systemctl restart okfine-api`（及 scheduler） |
| 只改了管理端 | `cd okfood-admin && npm ci && npm run build` |
| 只改了 H5 | 上传/同步到 `/var/www/okfood/h5` |
| 改了 Nginx | `sudo nginx -t && sudo systemctl reload nginx` |
| 数据库增量脚本 | `mysql ... meal_delivery < sql/migration_xxx.sql` → 再跑更新脚本或重启 API |
| 查看 API 报错 | `journalctl -u okfine-api -f` |

---

## 五、常见问题

### 抖音验券 500「兑换失败，请稍后重试」

多为 **`member_card_orders.pay_channel` 仍为 ENUM，不支持「抖音」**，开卡工单 INSERT 失败。执行迁移后重启 API，让用户**再次提交同一券码**（`grant_failed` 状态会断点续发奖）：

```bash
cd /var/www/okfood/backend
mysql -u root -p meal_delivery < sql/migration_045_member_card_orders_pay_channel_douyin.sql
sudo systemctl restart okfine-api
```

管理端「抖音核销记录」可查看 `error_msg`（常见含 `Data truncated` / `pay_channel`）。

### 本地已发奖 success，但抖音 App 仍显示「未核销」

多为 **旧版代码在 `prepare` 仍返回可用券时，误走「仅本地续发奖」、未再调抖音 `verify`**（并发撤销核销时尤易出现）。请：

1. 部署含修复的最新后端（`prepare` 成功必走 `verify`，发奖失败撤销前检查流水是否已为 `success`）。
2. 对已出问题订单做 **补偿核销**（不再重复发本地权益）：

```bash
cd /var/www/okfood/backend
.venv/bin/python scripts/douyin_compensate_verify.py \
  --order-id 121349085360194 \
  --code '用户券码明文' \
  --dry-run   # 确认后再去掉 --dry-run 执行
```

若补偿脚本报「券已核销」而本地也是 success，说明两侧已对齐，无需再操作。

### 访问 `/api` 返回 502

1. `sudo systemctl status okfine-api`
2. `curl http://127.0.0.1:8001/health`
3. `journalctl -u okfine-api -n 100 --no-pager`
4. 检查 Nginx 是否反代到 `127.0.0.1:8001`

### 浏览器 CORS 报错

`.env` 的 `CORS_ORIGINS` 须包含页面 Origin（如 `https://ok.sourcefire.cn`），保存后 `sudo systemctl restart okfine-api`。

### 管理端 / H5 子路由刷新 404

Nginx 对静态目录需配置 `try_files $uri $uri/ /index.html`（见 `docs/ok.source.cn.conf` 中 `/` 与 `/admin`）。

### 定时任务未执行

- 确认 `okfine-scheduler` 为 `active`：`systemctl status okfine-scheduler`
- 确认 **未** 在 API 进程内重复开调度（`ENABLE_IN_PROCESS_SCHEDULER=false`）
- **只运行一个** scheduler 实例

### `git pull` 失败

在服务器 `cd /var/www/okfood/backend` 处理冲突或改用 `SKIP_GIT=1` 仅重启服务；勿在生产目录做危险操作（如 `git reset --hard`）除非明确知晓后果。

---

## 六、相关文档

- [docs/生产部署与域名说明.md](../docs/生产部署与域名说明.md) — 域名、路径、环境一览
- [docs/前端接口联调说明.md](../docs/前端接口联调说明.md) — API 联调
- [README.md](../README.md) — 本地开发与项目结构
