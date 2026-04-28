"""顺丰同城 open 平台签名：开放平台「签名生成」演示为 `json & dev_id & 密钥`（单 &）后 MD5，再对 md5 十六进制字符串做 Base64。"""

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
    normalized = normalize_payload_for_sf_sign(obj)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=False, separators=(",", ":"))


def normalize_payload_for_sf_sign(obj: Any) -> Any:
    """
    与 ``json.dumps(..., sort_keys=True)`` 等价的递归规范化（便于与同一段 JSON 共用一致逻辑）。

    **不**改动 JSON 数组内元素顺序（与开放平台多数 Java 示例中 JSONArray 保序一致）。
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): normalize_payload_for_sf_sign(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [normalize_payload_for_sf_sign(x) for x in obj]
    return obj


def _md5_hex_upper(data: bytes) -> str:
    d = hashlib.md5(data).digest()
    return d.hex()  # 小写 hex，与多数 Java 示例中 Integer.toHexString 小写 nibble 一致


def generate_open_sign(json_string: str, dev_id: int, app_key: str) -> str:
    """
    生成 URL query `sign` 参数。

    与开放平台自助验签一致：**待加密串** = ``jsonString + \"&\" + str(dev_id) + \"&\" + appKey``（三段之间为**单**字符 ``&``），
    再对该串 UTF-8 做 MD5 → 小写十六进制串 → 对该十六进制串 UTF-8 字节做 Base64。
    """
    raw = f"{json_string}&{dev_id}&{app_key.strip()}"
    hex_str = _md5_hex_upper(raw.encode("utf-8"))
    return base64.b64encode(hex_str.encode("utf-8")).decode("ascii")


__all__ = ["generate_open_sign", "_canonical_json", "normalize_payload_for_sf_sign"]
