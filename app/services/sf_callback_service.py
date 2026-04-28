"""
顺丰同城开放平台：各类 HTTP 推送回调。

验签：`post_data` + ``&`` + ``dev_id`` + ``&`` + 密钥（顺丰与 PHP/Java 示例一致）；
``dev_id`` 优先取环境 ``SF_OPEN_DEV_ID``，若报文含 ``dev_id``/``devId`` 则一并尝试（与官方「按报文 dev_id」说明一致）。
部分推送为表单正文；``sign`` 在 URL ``?sign=``，亦可能仅在表单字段中。
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.sf_same_city_callback import SfSameCityCallback
from app.models.sf_same_city_push import SfSameCityPush
from app.services.sf_open.sign import _canonical_json, generate_open_sign, normalize_payload_for_sf_sign

logger = logging.getLogger(__name__)

# INFO 中单条正文预览长度（便于对齐顺丰侧 JSON；不含密钥）
_SF_CB_RAW_PREVIEW_CHARS = 600


def _sign_debug_preview(sign: str | None) -> str:
    """仅用于日志：长度 + 头尾片段（验签对齐时对照）。"""
    if not sign:
        return "(empty)"
    s = sign.strip()
    n = len(s)
    if n <= 36:
        return f"len={n} whole={s!r}"
    return f"len={n} head={s[:16]!r} tail={s[-12:]!r}"


def _body_debug_hints(raw_body: str) -> str:
    """正文边界特征：BOM / 首尾若干字符 repr，不换行泄密太多。"""
    if not raw_body:
        return "empty=True"
    parts: list[str] = []
    if raw_body.startswith("\ufeff"):
        parts.append("bom=True")
    head = raw_body[:48]
    tail = raw_body[-48:] if len(raw_body) > 48 else raw_body
    parts.append(f"head={head!r}")
    if tail != head:
        parts.append(f"tail={tail!r}")
    parts.append(f"utf8_bytes={len(raw_body.encode('utf-8'))}")
    return " ".join(parts)


def _raw_preview_one_line(raw_body: str, max_chars: int = _SF_CB_RAW_PREVIEW_CHARS) -> str:
    """单行可检索预览：过长则截断，便于与顺丰开放平台自助验签贴入。"""
    if not raw_body:
        return ""
    one = raw_body.replace("\r\n", "\n").replace("\n", "\\n")
    if len(one) <= max_chars:
        return one
    return one[:max_chars] + f"...(+{len(raw_body) - max_chars} chars)"


def _parse_form_post_body(raw_body: str) -> dict[str, str] | None:
    """顺丰部分回调为表单 POST（非 JSON）；与 ``parse_qsl`` 解析字段。"""
    s = raw_body.strip()
    if not s or "=" not in s:
        return None
    pairs = parse_qsl(s, keep_blank_values=True)
    if not pairs:
        return None
    out: dict[str, str] = {}
    for k, v in pairs:
        out[str(k)] = v
    return out


def _effective_sign_query(sign_query: str | None, payload: dict[str, Any] | None) -> str | None:
    """验签摘要：顺丰约定在 Query；表单回调可能只在 body 中携带 ``sign``。"""
    qs = (sign_query or "").strip()
    if qs:
        return qs
    if not payload:
        return None
    for key in ("sign", "Sign"):
        v = payload.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _form_sign_string_variants(raw_body: str) -> list[str]:
    """
    表单参与签名的待签串候选：常见于「排除 sign」「键序」与_wire 字面量差异。
    """
    s = raw_body.strip()
    if not s:
        return []
    pairs = parse_qsl(s, keep_blank_values=True)
    if not pairs:
        return []
    if not any(str(k).lower() != "sign" for k, _ in pairs):
        return []

    wo = [(str(k), v) for k, v in pairs if str(k).lower() != "sign"]
    if not wo:
        return []

    uniq: dict[str, str] = {}
    for k, v in wo:
        uniq[k] = str(v)

    cands: list[str] = []

    def add(x: str) -> None:
        if x and x not in cands:
            cands.append(x)

    add(urlencode(wo))
    sk = sorted(uniq.keys())
    add(urlencode([(k, uniq[k]) for k in sk]))

    parts_no_sign: list[str] = []
    for segment in s.split("&"):
        if not segment:
            continue
        name = segment.split("=", 1)[0]
        if name.lower() == "sign":
            continue
        parts_no_sign.append(segment)
    if parts_no_sign:
        add("&".join(parts_no_sign))

    out: list[str] = []
    for x in cands:
        if x and x not in out:
            out.append(x)
    return out


def _normalize_sign_from_query(sign_query: str) -> list[str]:
    """
    顺丰 sign 在 URL query 中；部分网关/框架会把 Base64 里的 ``+`` 变成空格，需与官方串比对。
    """
    s = sign_query.strip()
    out: list[str] = []
    for v in (s, unquote(s)):
        if not v:
            continue
        if v not in out:
            out.append(v)
        fixed = v.replace(" ", "+")
        if fixed != v and fixed not in out:
            out.append(fixed)
    return out


def _sign_match_one(expected_b64: str, wanted_candidates: list[str]) -> bool:
    """``secrets.compare_digest`` 仅接受等长字符串。"""
    for w in wanted_candidates:
        if len(expected_b64) != len(w):
            continue
        if secrets.compare_digest(expected_b64, w):
            return True
    return False


def _sign_match(raw_for_sign: str, sign_query: str, dev_id: int, app_key: str) -> bool:
    sig = generate_open_sign(raw_for_sign, dev_id, app_key)
    wanteds = _normalize_sign_from_query(sign_query)
    return _sign_match_one(sig, wanteds)


def _json_body_string_candidates(raw_body: str) -> list[str]:
    """
    待签串须与顺丰侧 ``json_encode`` 字节级一致。

    - 先试原文（顺丰一般无尾换行；若有则须与生成 sign 时一致）
    - 再试 ``strip()``，避免代理多塞 ``\\n`` 导致与原文不一致
    - 去 UTF-8 BOM（少数网关会加）
    """
    c: list[str] = []

    def add(x: str) -> None:
        if x and x not in c:
            c.append(x)

    add(raw_body)
    add(raw_body.strip())
    if raw_body.startswith("\ufeff"):
        add(raw_body.lstrip("\ufeff"))
    return c


def _dev_ids_for_verify(settings_dev: int, payload: dict[str, Any] | None) -> list[int]:
    """优先环境变量中的 dev_id；若 JSON 内带 dev_id（与官方「按报文 dev_id 取密钥」一致），一并尝试。"""
    out: list[int] = []
    if settings_dev:
        out.append(int(settings_dev))
    if not payload:
        return out
    for k in ("dev_id", "devId"):
        v = payload.get(k)
        if v is None or v == "":
            continue
        try:
            d = int(v)
        except (TypeError, ValueError):
            continue
        if d not in out:
            out.append(d)
    return out


def _dedupe_wire_strings(xs: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for x in xs:
        if x not in seen:
            seen.add(x)
            merged.append(x)
    return merged


def verify_sf_callback_signature(
    raw_body: str,
    sign_query: str | None,
    dev_ids: list[int],
    app_key: str,
) -> bool:
    """用多种待签串、多种 ``dev_id``、规范化后的 sign 尝试验签。"""
    if not sign_query or not raw_body.strip() or not dev_ids:
        return False
    body_cands = _dedupe_wire_strings(
        _json_body_string_candidates(raw_body) + _form_sign_string_variants(raw_body)
    )
    json_cands: list[str] = []
    try:
        obj = json.loads(raw_body)
        if isinstance(obj, dict):
            json_cands.append(_canonical_json(obj))
            # 少数推送侧可能对非 ASCII 做 \\uXXXX 转义，与_wire 字面量不同时用此条对齐
            json_cands.append(
                json.dumps(
                    normalize_payload_for_sf_sign(obj),
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
    except json.JSONDecodeError:
        pass
    for b in body_cands + json_cands:
        for did in dev_ids:
            if _sign_match(b, sign_query, did, app_key):
                return True
    return False


def _hint_verify_grid(raw_body: str, _payload: dict[str, Any] | None) -> str:
    """验签时尝试的 POST 串个数 × dev_id 个数，便于判断搜索空间。"""
    nw = len(_json_body_string_candidates(raw_body))
    nf = len(_form_sign_string_variants(raw_body))
    nj = 0
    try:
        o = json.loads(raw_body)
        if isinstance(o, dict):
            nj = 2
    except json.JSONDecodeError:
        pass
    return f"candidates_wire={nw} form_aliases={nf} json_repr_aliases={nj}"


def _extract_ids(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    shop_order_id = (
        payload.get("shop_order_id")
        or payload.get("shopOrderId")
        or payload.get("merchant_order_id")
    )
    shop_s = None
    if shop_order_id is not None:
        shop_s = str(shop_order_id)[:128]
    sf_order_id = (
        payload.get("sf_order_id")
        or payload.get("sfOrderId")
        or payload.get("order_id")
        or payload.get("sfBillId")
    )
    sf_s = None
    if sf_order_id is not None:
        sf_s = str(sf_order_id)[:64]
    return shop_s, sf_s


def persist_sf_callback_and_sync_push(
    db: Session,
    *,
    route_kind: str,
    raw_body: str,
    sign_ok: bool,
    payload: dict[str, Any] | None,
    verify_error: str | None,
) -> SfSameCityCallback:
    """写入回调日志；验签通过且命中推单记录时刷新最近顺丰字段。"""
    shop_order_id = None
    sf_order_id = None
    if payload:
        shop_order_id, sf_order_id = _extract_ids(payload)

    truncated = raw_body[:65000] if len(raw_body) > 65000 else raw_body
    row = SfSameCityCallback(
        route_kind=route_kind,
        sign_ok=sign_ok,
        error_message=(verify_error[:512] if verify_error else None),
        shop_order_id=shop_order_id,
        sf_order_id=sf_order_id,
        payload_json=payload,
        raw_body=truncated,
    )
    db.add(row)

    if sign_ok and payload:
        pus = None
        if shop_order_id:
            pus = db.scalar(select(SfSameCityPush).where(SfSameCityPush.shop_order_id == shop_order_id))
        if pus is None and sf_order_id:
            pus = db.scalar(select(SfSameCityPush).where(SfSameCityPush.sf_order_id == sf_order_id))
        if pus is not None:
            pus.last_callback_at = datetime.utcnow()
            pus.last_callback_kind = route_kind[:64]
            ost = payload.get("order_status")
            if ost is not None:
                try:
                    pus.sf_callback_order_status = int(ost)
                except (TypeError, ValueError):
                    pass

    db.commit()
    db.refresh(row)
    return row


def process_sf_notify(
    *,
    db: Session,
    route_kind: str,
    raw_body: str,
    sign_query: str | None,
    request_path: str | None = None,
    client_host: str | None = None,
    content_type: str | None = None,
    forwarded_for: str | None = None,
    query_param_keys: str | None = None,
    http_log_tag: str | None = None,
) -> tuple[bool, str | None]:
    """配送类订单回调：验签、落库；输出一条可调式 INFO trace（不包含密钥）。"""
    settings = get_settings()
    skip = bool(settings.SF_CALLBACK_SKIP_SIGN_VERIFY)
    settings_dev = int(settings.SF_OPEN_DEV_ID or 0)
    app_key = (settings.SF_OPEN_SECRET or "").strip()

    verify_err: str | None = None
    payload: dict[str, Any] | None = None
    if raw_body.strip():
        try:
            obj = json.loads(raw_body)
            if isinstance(obj, dict):
                payload = obj
        except json.JSONDecodeError:
            form_dict = _parse_form_post_body(raw_body)
            if form_dict is not None:
                payload = form_dict
            else:
                verify_err = "invalid body (neither JSON nor x-www-form-urlencoded)"
    else:
        verify_err = "empty body"

    dev_ids_try = _dev_ids_for_verify(settings_dev, payload)
    eff_sign = _effective_sign_query(sign_query, payload)

    if skip:
        sign_ok = verify_err is None and (payload is not None or raw_body.strip() == "{}")
    elif verify_err:
        sign_ok = False
    elif not app_key:
        verify_err = verify_err or "missing SF_OPEN_SECRET"
        sign_ok = False
    elif not eff_sign:
        verify_err = verify_err or "missing sign (URL query or form field sign)"
        sign_ok = False
    elif not dev_ids_try:
        verify_err = "missing dev_id(SF_OPEN_DEV_ID 或与报文 dev_id)"
        sign_ok = False
    else:
        sign_ok = verify_sf_callback_signature(raw_body, eff_sign, dev_ids_try, app_key)
        if not sign_ok:
            verify_err = verify_err or "sign mismatch"

    shop_tr, sf_tr = _extract_ids(payload) if payload else (None, None)
    keys_csv = ",".join(sorted(payload.keys())) if payload else ""
    grid = _hint_verify_grid(raw_body or "", payload)
    logger.info(
        "顺丰回调 trace http_tag=%s route_kind=%s path=%s query_keys=%s client=%s xff=%s content_type=%s "
        "skip_verify=%s sign_ok=%s err=%s settings_dev=%s dev_ids_try=%s has_secret=%s "
        "%s sign=%s body_hints=%s raw_preview=%s shop_order_id=%s sf_order_id=%s payload_keys=%s",
        http_log_tag or "-",
        route_kind,
        request_path or "-",
        query_param_keys or "-",
        client_host or "-",
        forwarded_for or "-",
        content_type or "-",
        skip,
        sign_ok,
        verify_err or "-",
        settings_dev,
        dev_ids_try,
        bool(app_key),
        grid,
        _sign_debug_preview(eff_sign or sign_query),
        _body_debug_hints(raw_body or ""),
        _raw_preview_one_line(raw_body or ""),
        shop_tr or "-",
        sf_tr or "-",
        keys_csv or "-",
    )

    try:
        persist_sf_callback_and_sync_push(
            db,
            route_kind=route_kind,
            raw_body=raw_body or "",
            sign_ok=sign_ok,
            payload=payload,
            verify_error=verify_err,
        )
    except Exception:
        logger.exception("顺丰回调落库失败 route_kind=%s", route_kind)
        db.rollback()
        raise

    return sign_ok, verify_err


def persist_oauth_style_callback(
    db: Session,
    *,
    route_kind: str,
    query_params: dict[str, str],
    raw_body: str,
) -> None:
    """授权类 URL 多为 GET query，无统一 sign 规则；仅落库备查。"""
    merged: dict[str, Any] = {"_query": query_params}
    rb = raw_body.strip()
    if rb:
        try:
            o = json.loads(rb)
            if isinstance(o, dict):
                merged.update(o)
        except json.JSONDecodeError:
            merged["_raw_post"] = rb[:5000]
    row = SfSameCityCallback(
        route_kind=route_kind,
        sign_ok=True,
        error_message="oauth_or_auth_callback_no_sign",
        shop_order_id=None,
        sf_order_id=None,
        payload_json=merged,
        raw_body=json.dumps(merged, ensure_ascii=False)[:65000],
    )
    db.add(row)
    db.commit()
