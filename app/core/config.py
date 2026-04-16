from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote_plus

from pydantic import model_validator
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
    JWT_EXPIRE_MINUTES_MEMBER: int = 60 * 24 * 7
    # 微信小程序一键登录专用：宜长于「短信登录」令牌，减少用户反复授权手机号（仍随卸载/清缓存失效）
    JWT_EXPIRE_MINUTES_MEMBER_WX_MINI: int = 60 * 24 * 365 * 10
    JWT_EXPIRE_MINUTES_COURIER: int = 60 * 24 * 30
    JWT_EXPIRE_MINUTES_ADMIN: int = 60 * 24

    CORS_ORIGINS: str = "http://localhost:5173"

    # 高德 Web 服务 Key（地理编码）：控制台须选「Web服务」类型
    AMAP_KEY: str = ""

    LOW_BALANCE_THRESHOLD: int = 2

    # 关闭时不校验短信通道配置、不注册验证码清理任务、短信登录接口返回 503
    SMS_ENABLED: bool = False

    # 短信：aliyun=阿里云短信；webhook=POST 到自建网关（JSON: phone, code）
    SMS_PROVIDER: Literal["aliyun", "webhook"] = "webhook"
    SMS_CODE_TTL_MINUTES: int = 5
    SMS_WEBHOOK_URL: str = ""
    SMS_WEBHOOK_TOKEN: str = ""

    ALIYUN_ACCESS_KEY_ID: str = ""
    ALIYUN_ACCESS_KEY_SECRET: str = ""
    ALIYUN_SMS_SIGN_NAME: str = ""
    ALIYUN_SMS_TEMPLATE_CODE: str = ""
    ALIYUN_SMS_ENDPOINT: str = "dysmsapi.aliyuncs.com"

    # 微信小程序：用于 code2Session + getuserphonenumber（手机号快速登录）
    WX_MINI_APPID: str = ""
    WX_MINI_SECRET: str = ""

    # 本地图片上传：静态资源根目录（磁盘上为 {UPLOAD_DIR}/static/uploads/images/...，URL 为 /static/uploads/images/...）
    UPLOAD_DIR: str = "data"
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024
    # 对外访问根地址（无尾部 /），上传写入库里的 image_url 会拼成绝对地址，如 https://api.example.com/static/uploads/...
    BASE_URL: str = ""
    # 兼容旧配置；仅当 BASE_URL 为空时生效
    PUBLIC_BASE_URL: str = ""

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
    def validate_sms_config(self) -> Any:
        if not self.SMS_ENABLED:
            return self
        if self.SMS_PROVIDER == "webhook":
            if not self.SMS_WEBHOOK_URL.strip():
                raise ValueError("SMS_PROVIDER=webhook 时必须配置非空的 SMS_WEBHOOK_URL")
        elif self.SMS_PROVIDER == "aliyun":
            missing = []
            if not self.ALIYUN_ACCESS_KEY_ID.strip():
                missing.append("ALIYUN_ACCESS_KEY_ID")
            if not self.ALIYUN_ACCESS_KEY_SECRET.strip():
                missing.append("ALIYUN_ACCESS_KEY_SECRET")
            if not self.ALIYUN_SMS_SIGN_NAME.strip():
                missing.append("ALIYUN_SMS_SIGN_NAME")
            if not self.ALIYUN_SMS_TEMPLATE_CODE.strip():
                missing.append("ALIYUN_SMS_TEMPLATE_CODE")
            if missing:
                raise ValueError(f"SMS_PROVIDER=aliyun 时必须配置: {', '.join(missing)}")
        return self

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
