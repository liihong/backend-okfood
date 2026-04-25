"""顺丰同城 open 平台签名：与常见 Java 示例 `jsonString + "&&" + devId + "&&" + appKey` 后 MD5，再对十六进制串做 Base64。"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any


def _canonical_json(obj: Any) -> str:
    """
    生成压缩且键有序的 JSON 字符串，作为待签名的「原始报文」。

    注意：不同语言/库的浮点/嵌套 key 序可能与顺丰示例不完全一致，若签名校验失败需对照官方 SignUtil 逐字节对齐。
    """
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _md5_hex_upper(data: bytes) -> str:
    d = hashlib.md5(data).digest()
    return d.hex()  # 小写 hex，与多数 Java 示例中 Integer.toHexString 小写 nibble 一致


def generate_open_sign(json_string: str, dev_id: int, app_key: str) -> str:
    """
    生成 URL query `sign` 参数。

    实现步骤与公开示例一致：utf-8 拼接 `json + "&&" + dev_id + "&&" + app_key` → MD5 二进制 →
    十六进制字符串 → 对该 hex 串 utf-8 字节做 Base64。
    """
    raw = f"{json_string}&&{dev_id}&&{app_key}"
    hex_str = _md5_hex_upper(raw.encode("utf-8"))
    return base64.b64encode(hex_str.encode("utf-8")).decode("ascii")


__all__ = ["generate_open_sign", "_canonical_json"]
