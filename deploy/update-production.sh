#!/usr/bin/env bash
# 生产环境增量更新：拉代码（可选）、安装 Python 依赖、重启 okfine-api；
# 可选在服务器上构建管理端 dist。
#
# 用法（在服务器上）：
#   bash /var/www/okfood/backend/deploy/update-production.sh
#   sudo bash /var/www/okfood/backend/deploy/update-production.sh
#
# 若当前用户无权执行 systemctl，请使用 sudo，或配置 passwordless sudo。
#
# 环境变量（可选）：
#   BACKEND_ROOT=/var/www/okfood/backend   后端根目录
#   SERVICE_NAME=okfine-api               systemd 服务名
#   VENV_PATH=$BACKEND_ROOT/.venv        Python 虚拟环境
#   SKIP_GIT=1                           跳过 git pull
#   BUILD_ADMIN=1                        构建 okfood-admin（需本机已安装 node/npm）

set -euo pipefail

BACKEND_ROOT="${BACKEND_ROOT:-/var/www/okfood/backend}"
SERVICE_NAME="${SERVICE_NAME:-okfine-api}"
SCHEDULER_SERVICE="${SCHEDULER_SERVICE:-okfine-scheduler}"
VENV_PATH="${VENV_PATH:-${BACKEND_ROOT}/.venv}"

systemctl_wrap() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

if [[ ! -d "${BACKEND_ROOT}" ]]; then
  echo "错误: 后端目录不存在: ${BACKEND_ROOT}" >&2
  exit 1
fi

cd "${BACKEND_ROOT}"

if [[ "${SKIP_GIT:-0}" != "1" ]] && [[ -d .git ]]; then
  echo ">>> git pull --ff-only"
  git pull --ff-only
elif [[ "${SKIP_GIT:-0}" != "1" ]]; then
  echo "提示: 未检测到 .git，跳过 git pull（无需时可设 SKIP_GIT=1 隐藏此提示）"
fi

if [[ ! -x "${VENV_PATH}/bin/pip" ]]; then
  echo "错误: 虚拟环境无效或不存在: ${VENV_PATH}（请先创建 .venv 并安装依赖）" >&2
  exit 1
fi

echo ">>> pip install -r requirements.txt"
"${VENV_PATH}/bin/pip" install -U pip
"${VENV_PATH}/bin/pip" install -r "${BACKEND_ROOT}/requirements.txt"

echo ">>> systemctl restart ${SERVICE_NAME}"
systemctl_wrap systemctl restart "${SERVICE_NAME}"
systemctl_wrap systemctl --no-pager -l status "${SERVICE_NAME}" || true

if systemctl_wrap systemctl cat "${SCHEDULER_SERVICE}" >/dev/null 2>&1; then
  echo ">>> systemctl restart ${SCHEDULER_SERVICE}"
  systemctl_wrap systemctl restart "${SCHEDULER_SERVICE}"
  systemctl_wrap systemctl --no-pager -l status "${SCHEDULER_SERVICE}" || true
else
  echo "提示: 未安装 ${SCHEDULER_SERVICE}.service，跳过 scheduler 重启（见 deploy/okfine-scheduler.service.example）"
fi

if [[ "${BUILD_ADMIN:-0}" == "1" ]]; then
  ADMIN_DIR="${BACKEND_ROOT}/okfood-admin"
  if [[ ! -f "${ADMIN_DIR}/package.json" ]]; then
    echo "错误: 管理端目录不存在或缺少 package.json: ${ADMIN_DIR}" >&2
    exit 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "错误: BUILD_ADMIN=1 但未找到 npm，请先安装 Node.js" >&2
    exit 1
  fi
  echo ">>> npm ci && npm run build (okfood-admin)"
  cd "${ADMIN_DIR}"
  npm ci
  npm run build
  echo ">>> 管理端构建产物目录: ${ADMIN_DIR}/dist"
fi

# 同步公开菜品库 H5 到站点根（Nginx root=/var/www/okfood/h5）
H5_ROOT="${H5_ROOT:-/var/www/okfood/h5}"
DISH_CATALOG_SRC="${BACKEND_ROOT}/h5/dish-catalog"
if [[ -d "${DISH_CATALOG_SRC}" ]]; then
  echo ">>> 同步菜品库 H5 → ${H5_ROOT}/dish-catalog"
  mkdir -p "${H5_ROOT}/dish-catalog"
  cp -a "${DISH_CATALOG_SRC}/." "${H5_ROOT}/dish-catalog/"
else
  echo "提示: 未找到 ${DISH_CATALOG_SRC}，跳过菜品库 H5 同步"
fi

echo ">>> 完成。API 健康检查（本机）:"
curl -sS "http://127.0.0.1:8001/health" || echo "(curl 失败，请检查服务与端口)"
