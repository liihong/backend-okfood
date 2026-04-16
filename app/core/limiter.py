"""全局限流（按客户端 IP）：防短信轰炸与暴力尝试登录。"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
