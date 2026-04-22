from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置：统一从环境变量 / .env 读取。数据库连接串仅在内存中组装，不在配置文件中写 URL。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "okfood-api"
    DEBUG: bool = False

    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "meal_delivery"
    MYSQL_CHARSET: str = "utf8mb4"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    # 小程序登录签发会员 JWT；默认约 10 年，可按安全策略改短
    JWT_EXPIRE_MINUTES_MEMBER: int = 60 * 24 * 365 * 10
    JWT_EXPIRE_MINUTES_COURIER: int = 60 * 24 * 30
    JWT_EXPIRE_MINUTES_ADMIN: int = 60 * 24

    CORS_ORIGINS: str = "http://localhost:5173"

    # 高德 Web 服务 Key（地理编码）：控制台须选「Web服务」类型
    AMAP_KEY: str = ""

    LOW_BALANCE_THRESHOLD: int = 2

    # 骑手配送费（元）：确认送达时累加 couriers.fee_pending；首份基础价 + 同地址每多一份加价
    COURIER_DELIVERY_BASE_YUAN: Decimal = Field(default=Decimal("4.00"), ge=Decimal("0"))
    COURIER_DELIVERY_EXTRA_PER_UNIT_YUAN: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0"))

    # 微信小程序：用于 code2Session + getuserphonenumber（手机号快速登录）
    WX_MINI_APPID: str = ""
    WX_MINI_SECRET: str = ""
    # 配送员确认送达后给会员下发订阅消息（需在公众平台申请模板，与下列字段名一致；留空则不下发）
    WX_MINI_SUBSCRIBE_DELIVERY_TMPL_ID: str = ""
    # 与模板中占位符 id 一致，逗号分隔，顺序对应：摘要、时间、说明（按你的模板增删）
    WX_MINI_SUBSCRIBE_DELIVERY_DATA_KEYS: str = "thing1,time2,thing3"
    # 点击通知打开的小程序路径（无开头 /）
    WX_MINI_SUBSCRIBE_PAGE: str = "pages/order/index"
    # formal | developer | trial
    WX_MINI_SUBSCRIBE_MINIPROGRAM_STATE: str = "formal"

    # 微信支付 v2（小程序 JSAPI）：商户平台 API密钥为32 位
    WECHAT_PAY_MCH_ID: str = ""
    WECHAT_PAY_API_KEY: str = ""
    # 异步通知完整 URL，须公网可访问，与商户平台配置一致，如 https://api.example.com/api/pay/wechat/notify
    WECHAT_PAY_NOTIFY_URL: str = ""
    # 微信回调来源 IP 段，逗号分隔 CIDR 或单 IP；留空则不做校验（仅建议开发环境）
    WECHAT_PAY_IP_WHITELIST: str = ""

    # 本地图片上传：静态资源根目录（磁盘上为 {UPLOAD_DIR}/static/uploads/images/...，URL 为 /static/uploads/images/...）
    UPLOAD_DIR: str = "data"
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024
    # 对外访问根地址（无尾部 /），上传写入库里的 image_url 会拼成绝对地址，如 https://api.example.com/static/uploads/...
    BASE_URL: str = ""
    # 兼容旧配置；仅当 BASE_URL 为空时生效
    PUBLIC_BASE_URL: str = ""

    # 对象存储：local=仅本地磁盘；aliyun=阿里云 OSS（已实现）；tencent/qiniu 等可后续扩展
    OSS_PROVIDER: str = "local"
    OSS_ENDPOINT: str = ""
    OSS_BUCKET: str = ""
    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""
    # 腾讯云等区域（当前仅 Aliyun 上传不使用，预留）
    OSS_REGION: str = ""
    # 自定义访问域名（无尾部 /），如 https://okoss.example.com；与 OSS_PUBLIC_BASE_URL 二选一，优先 OSS_PUBLIC_BASE_URL
    OSS_DOMAIN: str = ""
    # 对象键前缀，勿以 / 开头，勿以 / 结尾，如 okfood-prod
    OSS_KEY_PREFIX: str = "okfood"
    # 与 OSS_DOMAIN 等价用途（历史字段）；任一非空则作为文件对外 URL 前缀
    OSS_PUBLIC_BASE_URL: str = ""

    @property
    def oss_public_url_prefix(self) -> str:
        """头像等资源对外 URL 前缀（无尾部 /）。"""
        for raw in (self.OSS_PUBLIC_BASE_URL, self.OSS_DOMAIN):
            s = raw.strip().rstrip("/")
            if s:
                return s
        return ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [p.strip() for p in self.CORS_ORIGINS.split(",") if p.strip()]

    @property
    def sqlalchemy_database_url(self) -> str:
        """组装 SQLAlchemy 使用的连接 URL（密码中的 @ : 等特殊字符会自动转义）。"""
        user = quote_plus(self.MYSQL_USER)
        password = quote_plus(self.MYSQL_PASSWORD)
        return (
            f"mysql+pymysql://{user}:{password}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/"
            f"{self.MYSQL_DATABASE}?charset={quote_plus(self.MYSQL_CHARSET)}"
        )

    @property
    def upload_dir_resolved(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        if not p.is_absolute():
            p = Path.cwd() / p
        return p.resolve()

    @property
    def public_base_for_assets(self) -> str:
        """上传图片等资源的绝对 URL 前缀（无尾部 /）。"""
        b = self.BASE_URL.strip().rstrip("/")
        if b:
            return b
        return self.PUBLIC_BASE_URL.strip().rstrip("/")

    def public_url_for_upload_path(self, path: str) -> str:
        """path 形如 /static/uploads/images/2026/04/xxx.jpg"""
        if not path.startswith("/"):
            path = "/" + path
        base = self.public_base_for_assets
        if not base:
            return path
        return f"{base}{path}"

    @model_validator(mode="after")
    def validate_production_jwt_secret(self) -> Any:
        """生产环境禁止使用默认或过短的 JWT 密钥，避免令牌被伪造。"""
        if self.DEBUG:
            return self
        secret = self.JWT_SECRET.strip()
        if secret in {"", "change-me"} or len(secret) < 16:
            raise ValueError(
                "生产环境须设置 JWT_SECRET：不能使用默认值或空值，且建议长度不少于 16 个字符"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
