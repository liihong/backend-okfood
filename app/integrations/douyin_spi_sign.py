"""抖音生活服务 SPI 回调验签（新版 x-life-sign=sha256，旧版 URL sign=md5）。"""

from __future__ import annotations

import hashlib
import hmac
from typing import Mapping
from urllib.parse import parse_qsl


def build_spi_sign_string(*, client_secret: str, query_items: list[tuple[str, str]], body: bytes | None) -> str:
    """构造待签名字符串 str1（与官方 Go/Java 示例一致）。"""
    parts: list[str] = [client_secret]
    filtered: list[tuple[str, str]] = []
    for key, value in query_items:
        if key.lower() == "sign":
            continue
        filtered.append((key, value))
    filtered.sort(key=lambda kv: kv[0])
    for key, value in filtered:
        parts.append(f"{key}={value}")
    if body is not None:
        parts.append(f"http_body={body.decode('utf-8')}")
    return "&".join(parts)


def _normalize_query_items(query: Mapping[str, str | list[str] | None]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for key in query:
        raw = query.get(key)
        if raw is None:
            out.append((str(key), ""))
            continue
        if isinstance(raw, list):
            for item in sorted(str(v) for v in raw):
                out.append((str(key), item))
        else:
            out.append((str(key), str(raw)))
    return out


def compute_spi_new_signature(*, client_secret: str, query: Mapping[str, str | list[str] | None], body: bytes | None) -> str:
    str1 = build_spi_sign_string(
        client_secret=client_secret,
        query_items=_normalize_query_items(query),
        body=body,
    )
    return hashlib.sha256(str1.encode("utf-8")).hexdigest().lower()


def compute_spi_old_signature(*, client_secret: str, query: Mapping[str, str | list[str] | None], body: bytes | None) -> str:
    str1 = build_spi_sign_string(
        client_secret=client_secret,
        query_items=_normalize_query_items(query),
        body=body,
    )
    return hashlib.md5(str1.encode("utf-8")).hexdigest().lower()


def verify_spi_signature(
    *,
    client_secret: str,
    query: Mapping[str, str | list[str] | None],
    body: bytes | None,
    header_sign: str | None,
    query_sign: str | None,
) -> bool:
    """优先校验 Header 新签名，否则回退 URL 旧签名。"""
    secret = (client_secret or "").strip()
    if not secret:
        return False
    hs = (header_sign or "").strip().lower()
    if hs:
        expected = compute_spi_new_signature(client_secret=secret, query=query, body=body)
        return hmac.compare_digest(hs, expected)
    qs = (query_sign or "").strip().lower()
    if qs:
        expected = compute_spi_old_signature(client_secret=secret, query=query, body=body)
        return hmac.compare_digest(qs, expected)
    return False


def query_items_from_raw_query(raw_query: str) -> list[tuple[str, str]]:
    return list(parse_qsl(raw_query, keep_blank_values=True))
