"""顺丰开放平台 HTTP 推送：商户单号 / 顺丰单号 / 配送订单状态抽取（含嵌套 JSON）。

``sf_callback_service`` 与 ``resolve_sf_notify_app_key`` 必须共用同一套规则，
否则会「能解析 id 但不会用租户密钥验签」，导致回调落库 ``sign_ok=False`` 而无法自动履约。
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote

_NEST_PAYLOAD_KEYS = (
    "data",
    "result",
    "body",
    "content",
    "post_data",
    "postData",
)

_SHOP_ORDER_ID_KEYS = (
    "shop_order_id",
    "shopOrderId",
    "merchant_order_id",
    "merchantOrderId",
    "shop_order_no",
    "shopOrderNo",
)

_SF_ORDER_ID_KEYS = (
    "sf_order_id",
    "sfOrderId",
    "order_id",
    "orderId",
    "sf_bill_id",
    "sfBillId",
    "bill_id",
    "billId",
    "waybill_id",
    "waybillId",
)

_ORDER_STATUS_KEYS = (
    "order_status",
    "orderStatus",
    "delivery_status",
    "deliveryStatus",
)


def _parse_json_string(raw: str) -> Any | None:
    """解析嵌套在 data/content/post_data 等字段中的 JSON 字符串。"""
    s = (raw or "").strip()
    if not s or s[0] not in ("{", "["):
        return None
    for candidate in (s, unquote(s)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def normalize_sf_callback_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    展开嵌套 dict 与 JSON 字符串包装层，使 shop_order_id / order_status 等可在顶层读取。

    顺丰部分回调为 ``application/x-www-form-urlencoded``，业务 JSON 在 ``post_data`` 字段内。
    """
    if not isinstance(payload, dict) or not payload:
        return payload if isinstance(payload, dict) else {}

    out: dict[str, Any] = dict(payload)
    for k in _NEST_PAYLOAD_KEYS:
        v = out.get(k)
        if isinstance(v, dict):
            for ik, iv in v.items():
                if ik not in out:
                    out[ik] = iv
        elif isinstance(v, str):
            parsed = _parse_json_string(v)
            if isinstance(parsed, dict):
                for ik, iv in parsed.items():
                    if ik not in out:
                        out[ik] = iv
    return out


def payload_dict_layers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """顺丰常见：业务字段嵌套于 data / result / body / content / post_data。"""
    norm = normalize_sf_callback_payload(payload)
    layers: list[dict[str, Any]] = [norm]
    seen: set[int] = {id(norm)}

    def add_layer(obj: dict[str, Any]) -> None:
        oid = id(obj)
        if oid not in seen:
            seen.add(oid)
            layers.append(obj)

    for k in _NEST_PAYLOAD_KEYS:
        inner = norm.get(k)
        if isinstance(inner, dict):
            add_layer(inner)
        elif isinstance(inner, str):
            parsed = _parse_json_string(inner)
            if isinstance(parsed, dict):
                add_layer(parsed)
    return layers


def embedded_json_wire_strings(payload: dict[str, Any] | None) -> list[str]:
    """表单/JSON 包装层内嵌的业务 JSON 原文，作为验签待签串候选。"""
    if not payload:
        return []
    out: list[str] = []

    def add(s: str) -> None:
        t = s.strip()
        if t and t not in out:
            out.append(t)

    for k in _NEST_PAYLOAD_KEYS:
        v = payload.get(k)
        if isinstance(v, str):
            add(v)
            u = unquote(v)
            if u != v:
                add(u)
    return out


def _first_str_or_num_from_layers(layers: list[dict[str, Any]], keys: tuple[str, ...]) -> Any:
    for layer in layers:
        for key in keys:
            if key not in layer:
                continue
            v = layer[key]
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            return v
    return None


def extract_shop_and_sf_order_ids(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """与 ``sf_callback_service`` 原 ``_extract_ids`` 等价，供验签密钥解析共用。"""
    layers = payload_dict_layers(payload)
    shop_order_id = _first_str_or_num_from_layers(layers, _SHOP_ORDER_ID_KEYS)
    shop_s = str(shop_order_id)[:128] if shop_order_id is not None else None

    sf_order_id = _first_str_or_num_from_layers(layers, _SF_ORDER_ID_KEYS)
    sf_s = str(sf_order_id)[:64] if sf_order_id is not None else None
    return shop_s, sf_s


def _try_int_order_status(raw: Any) -> int | None:
    """避免 bool / 空白串误解析。"""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, float):
        try:
            n = int(raw)
            if n == raw:
                return n
            return None
        except (TypeError, ValueError):
            return None
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return n


def extract_order_status_shallow(payload: dict[str, Any]) -> int | None:
    """仅浅层嵌套键（与各层顶层键），与原 ``_extract_order_status`` 一致。"""
    layers = payload_dict_layers(payload)
    ost_raw = _first_str_or_num_from_layers(layers, _ORDER_STATUS_KEYS)
    return _try_int_order_status(ost_raw)


def extract_order_status_deep(payload: dict[str, Any], *, max_depth: int = 14) -> int | None:
    """
    在浅层未果时，对整棵 JSON 递归查找顺丰常用状态字段，
    解决 ``data.xxx.orderStatus`` 超出单层嵌套而无法触发妥投履约的问题。
    """
    norm = normalize_sf_callback_payload(payload)
    shallow = extract_order_status_shallow(norm)
    if shallow is not None:
        return shallow

    def walk(obj: Any, depth: int) -> int | None:
        if depth > max_depth:
            return None
        if isinstance(obj, dict):
            for k in _ORDER_STATUS_KEYS:
                if k in obj:
                    n = _try_int_order_status(obj.get(k))
                    if n is not None:
                        return n
            for v in obj.values():
                if isinstance(v, str):
                    parsed = _parse_json_string(v)
                    if parsed is not None:
                        n = walk(parsed, depth + 1)
                        if n is not None:
                            return n
                else:
                    n = walk(v, depth + 1)
                    if n is not None:
                        return n
        elif isinstance(obj, list):
            for item in obj:
                n = walk(item, depth + 1)
                if n is not None:
                    return n
        return None

    return walk(norm, 0)
