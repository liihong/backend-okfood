"""顺丰同城 openic 公网接口：签名、HTTP 调用。

与文档示例（JSON 体 + `&&` + dev_id + 密钥 再 MD5/Hex/Base64）一致。
线上若遇 sign 不通过，请与控制台样例或顺丰技术支持核对顺序与拼接符。
"""

from app.services.sf_open.client import SfOpenClient, SfOpenApiError
from app.services.sf_open.sign import generate_open_sign

__all__ = ["generate_open_sign", "SfOpenClient", "SfOpenApiError"]
