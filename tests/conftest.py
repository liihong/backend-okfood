"""pytest 启动前注入环境变量，避免加载本地 .env 时因生产校验或短信配置导致无法导入应用。"""

import os

# 必须在导入 `app` 包之前执行
os.environ["DEBUG"] = "true"
os.environ["JWT_SECRET"] = "pytest-jwt-secret-key-min-16-chars"
