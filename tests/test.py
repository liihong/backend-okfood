import secrets
import uuid

# 方法 A: 生成 32 字节的十六进制随机字符串（推荐，安全度高）
api_key_hex = secrets.token_hex(32)

# 方法 B: 生成 UUID4 格式（可读性好，常用于简单标识）
api_key_uuid = str(uuid.uuid4())

print(f"推荐密钥 (Hex): {api_key_hex}")
print(f"常用密钥 (UUID): {api_key_uuid}")